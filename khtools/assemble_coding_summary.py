import json

import pandas as pd
from khtools.constants_extract_coding import (
    LOW_COMPLEXITY_CATEGORIES, PROTEIN_CODING_CATEGORIES)
from khtools.log_utils import get_logger

logger = get_logger(__file__)


class AssembleSaveSummary:

    def __init__(
            self, filenames, csv, json_summary,
            peptide_bloom_filter_filename,
            alphabet, peptide_ksize, jaccard_threshold):
        self.filenames = filenames
        self.csv = csv
        self.json_summary = json_summary
        self.peptide_bloom_filter_filename = peptide_bloom_filter_filename
        self.alphabet = alphabet
        self.peptide_ksize = peptide_ksize
        self.jaccard_threshold = jaccard_threshold

    def maybe_write_csv(self, coding_scores):
        if self.csv:
            logger.info(
                "Writing coding scores of reads to {}".format(self.csv))
            coding_scores.to_csv(self.csv, index=False)

    def make_empty_coding_categories(self):
        coding_categories = dict.fromkeys(
            PROTEIN_CODING_CATEGORIES.values(), 0)
        molecule_low_complexity_key = LOW_COMPLEXITY_CATEGORIES[self.alphabet]
        coding_categories[molecule_low_complexity_key] = 0
        return coding_categories

    def maybe_write_json_summary(self, coding_scores):
        if not self.json_summary:
            # Early exit if json_summary is not True
            return
        empty_coding_categories = self.make_empty_coding_categories()

        if coding_scores.empty:
            summary = {
                'input_files': self.filenames,
                'jaccard_info': {
                    "count": 0,
                    "mean": None,
                    "std": None,
                    "min": None,
                    "25%": None,
                    "50%": None,
                    "75%": None,
                    "max": None
                },
                'classification_value_counts': empty_coding_categories,
                'classification_percentages': empty_coding_categories,
                'histogram_n_coding_frames_per_read': {
                    str(i): 0 for i in range(6)},
                'histogram_n_coding_frames_per_read_percentages': {
                    str(i): 0 for i in range(6)},
            }
        else:
            summary = self.generate_coding_summary(coding_scores)
        with open(self.json_summary, 'w') as f:
            logger.info(
                "Writing extract_coding summary to {}".format(
                    self.json_summary))
            json.dump(summary, fp=f)
        return summary

    def generate_coding_summary(self, coding_scores):
        translation_frame_percentages, translation_frame_counts = \
            self.get_n_translated_frames_per_read(coding_scores)

        files = coding_scores.filename.unique().tolist()

        classification_percentages, classification_value_counts = \
            self.get_n_per_coding_classification(coding_scores)

        # Get Jaccard distributions, count, min, max, mean, stddev, median
        jaccard_info = coding_scores.jaccard_in_peptide_db.describe().to_dict()
        summary = {
            'input_files': files,
            'jaccard_info': jaccard_info,
            'classification_value_counts':
                classification_value_counts,
            'classification_percentages':
                classification_percentages,
            'histogram_n_coding_frames_per_read':
                translation_frame_counts,
            'histogram_n_coding_frames_per_read_percentages':
                translation_frame_percentages,
            'peptide_bloom_filter': self.peptide_bloom_filter_filename,
            'peptide_alphabet': self.alphabet,
            'peptide_ksize': self.peptide_ksize,
            'jaccard_threshold': self.jaccard_threshold,
        }
        return summary

    def get_n_per_coding_classification(self, coding_scores):
        # Initialize to all zeros
        counts = self.make_empty_coding_categories()
        # Replace with observed sequences
        counts.update(
            coding_scores.classification.value_counts().to_dict())
        # Convert to series to make percentage calculation easy
        classifications = pd.Series(counts)

        # Initialize to all zeros
        percentages = self.make_empty_coding_categories()
        percentages_series = 100 * classifications / classifications.sum()
        # Replace with observations
        percentages.update(percentages_series.to_dict())
        return percentages, counts

    def get_n_translated_frames_per_read(self, coding_scores):
        """Of all coding sequences, get number of possible translations"""
        col = 'n_translated_frames'
        predicted_coding = coding_scores.query('classification == "Coding"')

        n_coding_per_read = predicted_coding.read_id.value_counts()
        n_coding_per_read.index = n_coding_per_read.index.astype(str)

        n_coding_per_read.name = col
        n_coding_per_read_df = n_coding_per_read.to_frame()

        # Number of reading frames per read, per filename
        coding_per_read_histogram = n_coding_per_read_df[col].value_counts()
        index = coding_per_read_histogram.index.astype(str)
        coding_per_read_histogram.index = \
            'Number of reads with ' + index + \
            " putative protein-coding translations"

        # Total number of coding reads
        total = coding_per_read_histogram.sum()

        coding_per_read_histogram_percentages = \
            100 * coding_per_read_histogram / total
        histogram_for_json = \
            coding_per_read_histogram.to_dict()
        percentages_for_json = \
            coding_per_read_histogram_percentages.to_dict()
        return percentages_for_json, histogram_for_json
