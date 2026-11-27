from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
from django.test import TestCase

from excel_reporters.scripts import utils


class ReportUtilitiesTests(TestCase):
    def setUp(self):
        self.base_data = pd.DataFrame(
            {
                "account": [
                    "100-000-000",
                    "100-001-000",
                    "100-002-000",
                    "200-000-000",
                    "200-001-000",
                ],
                "name": [
                    "OPERATING EXPENDITURES",
                    "Payroll",
                    "Supplies",
                    "CAPITAL EXPENDITURES",
                    "Equipment",
                ],
                "annual": [np.nan, 1200, 600, np.nan, 2400],
                "monthly": [np.nan, 100, 50, np.nan, 200],
            }
        )
        self.individual_reports = {
            "report_1": self.base_data.assign(
                exercised_this_month=[np.nan, 80, 40, np.nan, 180]
            ),
            "report_2": self.base_data.assign(
                exercised_this_month=[np.nan, 90, 60, np.nan, 120]
            ),
        }

    def make_result(self):
        reports = {
            name: report.copy(deep=True)
            for name, report in self.individual_reports.items()
        }
        return utils.result_calculation(reports, month=2)

    def test_generate_single_expenditures_adds_deterministic_monthly_amounts(self):
        random_values = np.array([0.1, 0.25, 0.75, 0.2, 0.5])
        rng = Mock()
        rng.uniform.return_value = random_values

        with patch.object(utils.np.random, "default_rng", return_value=rng):
            result = utils.generate_single_expenditures(self.base_data.copy())

        expected = (
            pd.to_numeric(self.base_data["monthly"], errors="coerce")
            * random_values
        ).rename("exercised_this_month")
        pd.testing.assert_series_equal(result["exercised_this_month"], expected)

    def test_generate_bulk_expenditures_returns_independent_monthly_reports(self):
        random_values = [
            np.array([0.1, 0.2, 0.3, 0.4, 0.5]),
            np.array([0.5, 0.4, 0.3, 0.2, 0.1]),
        ]
        rngs = [Mock(), Mock()]
        for rng, values in zip(rngs, random_values):
            rng.uniform.return_value = values

        with patch.object(
            utils.np.random, "default_rng", side_effect=rngs
        ) as default_rng:
            reports = utils.generate_bulk_expenditures(2, self.base_data)

        self.assertEqual(list(reports), ["report_1", "report_2"])
        self.assertIsNot(reports["report_1"], reports["report_2"])
        self.assertEqual(default_rng.call_count, 2)
        self.assertNotIn("exercised_this_month", self.base_data.columns)
        for index, name in enumerate(reports):
            expected = (
                self.base_data["monthly"] * random_values[index]
            ).rename("exercised_this_month")
            pd.testing.assert_series_equal(
                reports[name]["exercised_this_month"], expected
            )

    def test_result_calculation_computes_current_month_and_ytd_values(self):
        result = self.make_result()
        payroll = result.loc[result["Account Code"] == "100-001-000"].iloc[0]
        supplies = result.loc[result["Account Code"] == "100-002-000"].iloc[0]

        self.assertEqual(payroll["Current-Month Actual Expenditures"], 90)
        self.assertAlmostEqual(payroll["Current-Month Budget Utilization (%)"], 0.9)
        self.assertEqual(payroll["YTD Actual Expenditures"], 170)
        self.assertEqual(payroll["Remaining Annual Budget"], 1030)
        self.assertAlmostEqual(
            payroll["YTD Expenditures as % of Annual Budget"], 170 / 1200
        )

        self.assertAlmostEqual(supplies["Current-Month Budget Utilization (%)"], 1.2)
        self.assertEqual(supplies["YTD Actual Expenditures"], 100)

    def test_final_touches_adds_category_subtotals(self):
        final_report = utils.final_touches(self.make_result())
        subtotals = final_report.loc[
            final_report["Account Description"] == "SUBTOTAL"
        ]

        self.assertEqual(len(subtotals), 2)
        operating_subtotal = subtotals.iloc[0]
        self.assertEqual(operating_subtotal["Approved Annual Budget"], 1800)
        self.assertEqual(operating_subtotal["YTD Actual Expenditures"], 270)
        self.assertAlmostEqual(
            operating_subtotal["YTD Expenditures as % of Annual Budget"], 0.15
        )

    def test_summary_report_groups_accounts_and_adds_grand_total(self):
        summary = utils.summary_report(self.make_result())
        payroll = summary.loc[summary["Account Description"] == "Payroll"].iloc[0]
        grand_total = summary.loc[
            summary["Account Description"] == "GRAND TOTAL"
        ].iloc[0]

        self.assertEqual(payroll["Current-Month Actual Expenditures"], 90)
        self.assertEqual(payroll["YTD Actual Expenditures"], 170)
        self.assertAlmostEqual(
            payroll["YTD Expenditures as % of Annual Budget"], 170 / 1200
        )
        self.assertEqual(payroll["Remaining Annual Budget"], 1030)
        self.assertEqual(grand_total["Approved Annual Budget"], 4200)
        self.assertEqual(grand_total["YTD Actual Expenditures"], 570)
