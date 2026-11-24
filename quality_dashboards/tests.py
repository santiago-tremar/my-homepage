from django.test import TestCase
from django.urls import reverse

from .models import ProcessMap


class StationListViewTests(TestCase):
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
