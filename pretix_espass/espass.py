import tempfile
from collections import OrderedDict
from typing import Tuple
import os
import shutil
import json
from shutil import make_archive
from django import forms
from django.utils.translation import ugettext, ugettext_lazy as _
from django.core.files.storage import default_storage
from pretix.base.models import Order
from pretix.base.ticketoutput import BaseTicketOutput
from pretix.multidomain.urlreverse import build_absolute_uri
from wallet.models import Barcode, BarcodeFormat, EventTicket, Location, Pass

from .forms import PNGImageField


class EspassOutput(BaseTicketOutput):
    identifier = 'espass'
    verbose_name = 'esPass Tickets'
    download_button_icon = 'fa-mobile'
    download_button_text = 'esPass'

    @property
    def settings_form_fields(self) -> dict:
        return OrderedDict(
            list(super().settings_form_fields.items()) + [
                ('icon',
                 PNGImageField(
                     label=_('Event icon'),
                     help_text=_('We suggest an upload size of 96x96 pixels - the display size is 48dp'),
                     required=True,
                 )),
                ('logo',
                 PNGImageField(
                     label=_('Event logo'),
                     help_text=_('Upload a nice big image - size depends on the device - example size 800x600'),
                     required=True,
                 )),
                ('location_name',
                 forms.CharField(
                     label=_('Event location name'),
                     required=False
                 )),
                ('latitude',
                 forms.FloatField(
                     label=_('Event location latitude'),
                     required=False
                 )),
                ('longitude',
                 forms.FloatField(
                     label=_('Event location longitude'),
                     required=False
                 )),
            ]
        )

    def generate(self, order_position: Order) -> Tuple[str, str, str]:
        order = order_position.order

        temp_in = tempfile.mkdtemp()
        temp_out = tempfile.mkdtemp()

        ticket = str(order_position.item)
        if order_position.variation:
            ticket += ' - ' + str(order_position.variation)

        pass_id = '%s-%s' % (order.event.slug, order.code)

        data = {'type': 'EVENT',
                'description': str(order.event.name),
                'id': pass_id,
                'wtf': "1",
                'locations': [

                ],
                'fields': [
                    {
                        "hide": False,
                        "label": ugettext('Product'),
                        "value": ticket
                    },
                    {
                        "hide": True,
                        "label": ugettext('Ordered by'),
                        "value": order.email
                    },
                    {
                        "hide": True,
                        "label": ugettext('Order code'),
                        "value": order.code
                    },
                    {
                        "hide": True,
                        "label": ugettext('Organizer'),
                        "value": str(order.event.organizer)
                    },
                ]
                }

        if order_position.attendee_name:
            data["fields"].append({
                "label": ugettext('Attendee name'),
                "value": order_position.attendee_name,
                "hide": False
            })

        if order.event.settings.contact_mail:
            data["fields"].append({
                "label": ugettext('Organizer contact'),
                "value": order.event.settings.contact_mail,
                "hide": False
            })

        if self.event.settings.ticketoutput_espass_latitude and self.event.settings.ticketoutput_espass_longitude:
            data["locations"].append({
                "name": self.event.settings.ticketoutput_espass_location_name,
                "lat": self.event.settings.ticketoutput_espass_latitude,
                "lon": self.event.settings.ticketoutput_espass_longitude
            })

        icon_file = self.event.settings.get('ticketoutput_espass_icon')
        read = default_storage.open(icon_file.name, 'rb').read()
        open(os.path.join(temp_in, 'icon.png'), 'wb').write(read)

        icon_file = self.event.settings.get('ticketoutput_espass_logo')
        read = default_storage.open(icon_file.name, 'rb').read()
        open(os.path.join(temp_in, 'logo.png'), 'wb').write(read)

        with open(os.path.join(temp_in, 'main.json'), 'w') as outfile:
            json.dump(data, outfile, indent=4, separators=(',', ':'))

        zip_file = make_archive(
            os.path.join(temp_out, 'zipfile_name'),
            'zip',
            root_dir=temp_in,
        )

        filename = 'foo_{}-{}.espass'.format(order.event.slug, order.code)

        zip_content = open(zip_file, "rb").read()
        self.cleanup(temp_in, temp_out)

        return filename, 'application/vnd.espass-espass+zip', zip_content

    @staticmethod
    def cleanup(temp_in, temp_out):
        shutil.rmtree(temp_in)
        shutil.rmtree(temp_out)
