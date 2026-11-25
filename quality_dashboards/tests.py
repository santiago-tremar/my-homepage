from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from datetime import date
import pandas as pd

from .models import ProcessMap, RawData
from .forms import StationProcessForm, RawDataForm
from .scripts.utils import get_family_selection
from .scripts.yields import base_dataframe_cleanup, calculate_yield_by_loop



class StationManagerTests(TestCase):
    def setUp(self):
        self.family_station = ProcessMap.objects.create(
            family='Audi',
            station_type='Assembly',
            operation_id=0,
        )

    def test_station_map_model(self):
        self.assertEqual(self.family_station.family, 'Audi')
        self.assertEqual(self.family_station.station_type, 'Assembly')
        self.assertFalse(self.family_station.operation_id)

    def test_station_map_view(self):
        response = self.client.get(reverse('station-manager'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Station Manager')
        self.assertTemplateUsed(response, 'dashboard_config.html')
        self.assertContains(response, 'Audi')
        self.assertContains(response, 0)

    def test_station_map_url_mappings(self):
        response = self.client.get('/demo/quality/stations/?family=Audi')
        alternate_response = self.client.get('/demo/quality/stations/?family=Nissan')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(alternate_response.status_code, 200) ## Wrong Family names in URL fall-back to first item in list, which is Audi in this case.
        self.assertContains(alternate_response, 'Audi')  ## Idem.

    def test_valid_update_displays_saved_message(self):
        station = ProcessMap.objects.create(
            family="Alpha",
            station_type="Station A",
            operation_id=0,
        )

        response = self.client.post(
            f'{reverse("station-manager")}?family=Alpha',
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(station.pk),
                "form-0-operation_id": "42",
                "form-0-result_filter": "on",
            },
            follow=True,
        )

        self.assertContains(response, "Changes saved.")
        station.refresh_from_db()
        self.assertEqual(station.operation_id, 42)
        self.assertTrue(station.result_filter)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha')
        self.assertFalse(self.family_station.operation_id) ## Check 'Audi' is still set to False.
        self.assertEqual(self.family_station.operation_id, 0)


class StationManagerFormTests(TestCase):
    def setUp(self):
        self.family_station = ProcessMap.objects.create(
                    family='Audi',
                    station_type='Assembly',
                    operation_id=0,
                )
        
    def test_form_validation(self):
        form = StationProcessForm(
            data={
                "operation_id": "ABC",
                "result_filter": "on",
            },
            instance=self.family_station,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("operation_id", form.errors)
        self.family_station.refresh_from_db()
        self.assertEqual(self.family_station.operation_id, 0)

class RawDataFormTests(TestCase):
    def setUp(self):
        self.good_upload = SimpleUploadedFile(
            'stations.csv',
            b'PartFamily,Station\nAlpha,Assembly\n',
            content_type='text/csv',
        )
        self.good_form = RawDataForm(
            data={'name': 'Test data'},
            files={'upload': self.good_upload},
        )

        self.bad_upload = SimpleUploadedFile(
            'stations.csv',
            b'PartFamily,User\nAlpha,johndoe\n',
            content_type='text/csv',
        )
        self.bad_form = RawDataForm(
            data={'name': 'Test data'},
            files={'upload': self.bad_upload},
        )

    def test_raw_data_form_validation(self):
        self.assertTrue(self.good_form.is_valid())
        self.assertEqual(self.good_form.process_map_pairs,[('Alpha', 'Assembly')])
        self.assertFalse(self.bad_form.is_valid())


class YieldViewTests(TestCase):
    """ Test the Yield Report view. Including calculation logic. """

    def setUp(self):
        ProcessMap.objects.create(
            family='Alpha',
            station_type='Assembly',
            operation_id=1,
            result_filter=True,
        )
        ProcessMap.objects.create(
            family='Alpha',
            station_type='Tester',
            operation_id=2,
            result_filter=True,
        )
        ProcessMap.objects.create(
            family='Alpha',
            station_type='Excluded Station',
            operation_id=3,
            result_filter=False,
        )
        ProcessMap.objects.create(
            family='Beta',
            station_type='Assembly',
            operation_id=1,
            result_filter=True,
        )

        csv_data = (
            'PartFamily,Station,SerialNumber,TestSequence,TestTime,GlobalTestResult\n'
            'Alpha,Assembly,ASSY-1,1,06/01/2024 08:00:00,PASS\n'
            'Alpha,Tester,TEST-1,1,06/01/2024 08:00:00,FAIL\n'
            'Alpha,Tester,TEST-1,2,06/01/2024 09:00:00,PASS\n'
            'Alpha,Tester,TEST-1,2,06/01/2024 09:00:00,FAIL\n'
            'Alpha,Excluded Station,EXCLUDED-1,1,06/01/2024 08:00:00,PASS\n'
            'Beta,Assembly,BETA-1,1,06/01/2024 08:00:00,PASS\n'
        ).encode()
        raw_data = RawData.objects.create(
            name='Yield test data',
            upload=SimpleUploadedFile(
                'yield-test.csv',
                csv_data,
                content_type='text/csv',
            ),
        )
        self.addCleanup(raw_data.upload.delete, save=False)

    def test_family_selection_uses_requested_family(self):
        request = RequestFactory().get('/', {'family': 'Beta'})

        families, selected_family = get_family_selection(request)

        self.assertEqual(families, ['Alpha', 'Beta'])
        self.assertEqual(selected_family, 'Beta')

    def test_base_dataframe_cleanup_filters_and_assigns_test_loops(self):
        dataframe = base_dataframe_cleanup('Alpha')

        self.assertEqual(len(dataframe), 3)
        self.assertEqual(set(dataframe['Station']), {'Assembly', 'Tester'})
        self.assertEqual(
            dataframe.loc[dataframe['Station'] == 'Tester', 'AggregatedTestLoop'].tolist(),
            [1, 2],
        )
        self.assertEqual(set(dataframe['TestDate']), {date(2024, 1, 6)})

    def test_calculate_yield_by_loop_returns_expected_counts_and_rty(self):
        dataframe = base_dataframe_cleanup('Alpha')
        process_map_index = pd.Series({'Assembly': 1, 'Tester': 2})
        test_date = date(2024, 1, 6)

        fpy, fpy_rty = calculate_yield_by_loop(dataframe, 1, process_map_index)
        tpy, tpy_rty = calculate_yield_by_loop(dataframe, 3, process_map_index)

        self.assertEqual(fpy.loc[(1, 'Assembly'), (test_date, 'PASS')], 1)
        self.assertEqual(fpy.loc[(2, 'Tester'), (test_date, 'FAIL')], 1)
        self.assertEqual(fpy.loc[(2, 'Tester'), (test_date, 'YIELD')], '0.00%')
        self.assertEqual(tpy.loc[(2, 'Tester'), (test_date, 'PASS')], 1)
        self.assertEqual(tpy.loc[(2, 'Tester'), (test_date, 'YIELD')], '100.00%')
        self.assertEqual(fpy_rty[test_date], 0)
        self.assertEqual(tpy_rty[test_date], 100)

    def test_yield_view_renders_correct_results(self):
        response = self.client.get(reverse('yields'), {'family': 'Alpha'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard_yields.html')
        self.assertContains(response, 'First Pass Yield')
        self.assertContains(response, 'Test Station Yield without False Calls')
        self.assertContains(response, 'Assembly')
        self.assertContains(response, 'Tester')
        self.assertEqual(response.context['selected_family'], 'Alpha')
        self.assertEqual(response.context['fpy_rty_values'], ['0.00%'])
        self.assertEqual(response.context['tpy_rty_values'], ['100.00%'])

        tpy_tester = next(
            row for row in response.context['tpy_rows']
            if row['station_type'] == 'Tester'
        )
        self.assertEqual(tpy_tester['cells'], [0, 1, 1, '100.00%'])
