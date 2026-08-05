from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Driver, TransportRoute, Trip, Vehicle


class TransportModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="transport-test",
            password="safe-test-password",
        )
        self.route = TransportRoute.objects.create(
            origin="Moshi",
            destination="Arusha",
            default_price=Decimal("120000.00"),
            distance_km=Decimal("80.00"),
        )
        self.vehicle = Vehicle.objects.create(plate_number="T 123 ABC")
        self.driver = Driver.objects.create(
            first_name="Test",
            last_name="Driver",
            phone="0700000000",
            license_number="LIC-001",
        )

    def test_trip_balance_and_payment_status(self):
        trip = Trip.objects.create(
            route=self.route,
            origin=self.route.origin,
            destination=self.route.destination,
            vehicle=self.vehicle,
            driver=self.driver,
            amount_charged=Decimal("120000.00"),
            amount_paid=Decimal("50000.00"),
            created_by=self.user,
        )
        self.assertEqual(trip.payment_status, Trip.PaymentStatus.PARTIAL)
        self.assertEqual(trip.balance_due, Decimal("70000.00"))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("transport-dashboard"))
        self.assertEqual(response.status_code, 302)
