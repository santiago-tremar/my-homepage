from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import ProcessMap
from .forms import StationProcessForm, RawDataForm



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
        