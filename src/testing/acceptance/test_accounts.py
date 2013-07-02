import unittest
from nose.plugins.attrib import attr

import cloudsigma.resource as cr
from cloudsigma.conf import config


@attr('acceptance_test')
class LoginTest(unittest.TestCase):
    def test_profile(self):
        """Test login and getting user profile

        """
        r = cr.Profile()
        profile = r.get()
        self.assertNotEqual(profile, {}, 'Invalid profile returned')
        self.assertEqual(profile['email'], config['username'], 'Profile returned invalid email')
        self.assertIn(profile['state'], ('REGULAR', 'NEW_USER', 'TRIAL'), 'Profile returned invalid state')
