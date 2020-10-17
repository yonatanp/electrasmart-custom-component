Electra Smart Custom Component
==

HomeAssistant custom component to support Electra Smart air conditioners.

This is based on the `electrasmart` python library. Both are in alpha stage at best. Use at your own risk and please report back your results, preferably as issues.

Setup
--

Before you begin, you will need to get auth credentials (imei + token) and discover your AC device IDs that will later be used by the HomeAssistant configuration.

Install the client library with e.g. `pip install electrasmart` on any machine.

Then, run `electrasmart-auth`, and provide a phone number that has been pre-authorized in the official ElectraSmart mobile app.
You will be requested to provide an OTP sent via SMS.
Once this is complete, you will be provided with two strings: `imei` and `token`. Write them down for later.

Next, run `electrasmart-list-devices <imei> <token>` to get a list of your devices. Pick the right ID of the AC unit you want to manage in HomeAssistant. Write it down for later.

Next, copy the `electrasmart` folder found in this repository into your HomeAssistant deployment under `/PATH_TO_CONFIG/custom_components`. If the `custom_components` folder does not exist, create it empty first. If done correctly, the file `/PATH_TO_CONFIG/custom_components/electrasmart/manifest.json` should exist.

Next, add configuration to the `configuration.yaml` such as the following:

```yaml
...
climate:
  - platform: electrasmart
    name: MyLivingRoomAC
    imei: "2b9500000..."
    token: "1fd4a2e86..."
    ac_id: 12345
...
```

Note: if you want to configure multiple ACs under the same account, this is possible. Do it in the same way you configure multiple instances of the same type of platform in HomeAssistant (e.g. add another item under climate). The `imei` and `token` values should be the same for both ACs.

Troubleshooting
--

It will probably not work out of the box just yet. It is recommended that you enable detailed logging by adding the following configuration to your `configuration.yaml` while debugging the setup process:
```yaml
...
logger:
  default: warn
  logs:
    custom_components.electrasmart: debug
...
```

See more details on the [Logger integration](https://www.home-assistant.io/integrations/logger/) in the official docs.
