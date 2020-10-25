# Electra Smart Custom Component
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)


## Description
HomeAssistant custom component to support Electra Smart air conditioners.

This is based on the `electrasmart` python library. Both are in alpha stage at best. Use at your own risk and please report back your results, preferably as issues.

+  Supports [HACS](https://github.com/custom-components/hacs) installation


## Installation
Install through [HACS](https://hacs.xyz/):

1. Go to HACS -> Settings.
1. Enter "https://github.com/yonatanp/electrasmart-custom-component" for _ADD CUSTOM REPOSITORY_ and choose "Integration" for _Category_.
1. Click Save.

Or, install manually by downloading the `custom_components/electrasmart` folder from this repo and placing it in your `config/custom_components/` folder. If the `custom_components` folder does not exist, create it empty first. If done correctly, the file `config/custom_components/electrasmart/manifest.json` should exist.


## IMEI and Token
Before you configure the integration, you will need to get auth credentials (IMEI + token) and discover your AC device IDs that will later be used by the HomeAssistant configuration.

Install the client library with e.g. `pip install electrasmart` on any machine.

Then, run `electrasmart-auth`, and provide a phone number that has been pre-authorized in the official ElectraSmart mobile app.
You will be requested to provide an OTP sent via SMS.
Once this is complete, you will be provided with two strings: `imei` and `token`. Write them down for later.

Next, run `electrasmart-list-devices <imei> <token>` to get a list of your devices. Pick the right ID of the AC unit you want to manage in HomeAssistant. Write it down for later.


## Configuration
Add configuration to the `configuration.yaml` such as the following:

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

## Troubleshooting

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