# AWS-Re/Start-ML-Irrigation-System
Final project for AWS Re/Start course. Consists of an automated plant irrigation system that uses sensors to collect soil moisture data, then feed a Decision Tree machine learning model to classify whether the plant needs watering or not.

Presentation video: https://youtu.be/bRBd4tIgXfQ

Usage
Install virtual environment so the packages needed for this to work don't conflict with existing versions on your OS.
First, create a folder which will hold the virtual environment, then navigate to it.

For Linux:
sudo apt-get install python-pip
pip install virtualenv
virtualenv "venv_name"
source venv_name/bin/activate

For Windows:
pip install virtualenv 
python -m venv myenv
myenv\Scripts\activate

After you have it running, you need to install the libraries used for this project to work:
pip3 install --upgrade jupyter matplotlib numpy pandas scipy scikit-learn flask watchdog requests

Then check if the install went wrong with:
python3 -c "import jupyter, matplotlib, numpy, pandas, scipy, sklearn"

If nothing shows up, it's because it installed properly. Now navigate to where you created your virtual environment folder then type:
jupyter	notebook

Download the files uploaded on the folder section and put them in the folder you created at start.

On the same venv folder, run:
python app.py

This will create the API to receive POST requests.

Before running the post.py script, you need to set these environment variables (the credentials are no longer hardcoded in the file):
$env:CSV_FILE = "soil_moisture_data.csv"
$env:API_ENDPOINT = "http://127.0.0.1:5000/predict"   # use the Pi's LAN IP if post.py runs on another machine
$env:EMAIL_SENDER = "your_email@gmail.com"
$env:EMAIL_PASSWORD = "your_google_apps_password"     # only works with Google app passwords
$env:EMAIL_RECIPIENT = "recipient_email@gmail.com"

After you made this changes, save the file and now you can run this script:
python post.py

This will listen to new changes made to the .csv file (you can do it manually or it can be the data sent via sensors)

Now to test the deployed model, edit the .csv file with a new entry (make it so the model predicts with "water" so you recieve the e-mail)

---

# Model architecture: Regar = Thirsty AND Can_Water

A single tree trained on `Water_Needed` could not learn the rule, because the
label is a **conjunction** of a per-plant threshold and a time window, and the
positive class was a small minority. Instead we train two small trees and
combine them at inference time:

| Tree | Features | Learns |
|------|----------|--------|
| `Thirsty`   | `Plant_Type`, `Moisture_Percentage` | moisture below the plant's minimum |
| `Can_Water` | `Plant_Type`, `Moisture_Percentage`, `Hour` | outside the 11:00–16:00 no-water window (sun overhead) |

`Regar = Thirsty AND Can_Water`. Emergency exception: if the soil is drier than
`min_threshold - CRITICAL_DELTA` the plant is watered even inside the window,
because waiting until 16:00 could kill it (`CRITICAL_DELTA = 100` disables it).

## Single source of truth: `etiquetas.py`

All business rules live in `etiquetas.py` (plant codes/names, thresholds,
no-water window, emergency delta). `entrenar_modelo.py`, `ejecutar_sensor.py`,
`modelo.py` and `app.py` all import from it, so labels and inference can never
drift apart again.

Important details:

* `Hour` must be **decimal** (`18:30` -> `18.5`); with integer hours the 16:00
  boundary is unlearnable. `etiquetas.normalize_hour` accepts `14`, `14.5`,
  `"14:30"` and `"14:30:00"`.
* `Plant_Type` in the CSV is **text** (`Hierba`), not a number. Names with or
  without accents and the legacy codes `0..3` are all accepted.
* The old `.pkl` (single `DecisionTreeClassifier`) is rejected on purpose:
  run `python entrenar_modelo.py` once to regenerate the dict bundle.

## Running

```bash
python entrenar_modelo.py          # trains both trees, saves .pkl + metadata
python app.py                      # API on 0.0.0.0:5000
python ejecutar_sensor.py          # on the Raspberry Pi (real sensor)
python ejecutar_sensor.py --demo --once   # on a PC, no hardware needed
python -m unittest test_riego -v   # 13 tests (API tests skip if app.py is down)
```

API contract:

```bash
curl -X POST http://127.0.0.1:5000/predict -H "Content-Type: application/json" \
     -d '{"Moisture_Percentage": 30, "Hour": "14:30", "Plant_Type": "Hierba"}'
# {"prediction":"No regar","regar":false,"thirsty":1,"can_water":0,
#  "in_no_water_window":true,"plant_type":"Hierba","hour":14.5,"thresholds":[40.0,80.0], ...}

curl http://127.0.0.1:5000/health
```

## Deployment on the Raspberry Pi

See [`deploy/README.md`](deploy/README.md). Three systemd **user** services
(`riego-api`, `riego-sensor`, `riego-post`) with `loginctl enable-linger aru`,
so they keep running after the SSH session closes and after a reboot.

* `DISCORD_WEBHOOK_URL` lives in `.env` (git-ignored); `riego-sensor` and
  `riego-post` load it via `EnvironmentFile`.
* `cap_config.json` (sensor calibration) is also git-ignored and must exist on
  the Pi before `ejecutar_sensor.py` starts.
* `app.py` runs with `debug=False` unless `DEBUG=1`: Werkzeug's reloader starts a
  second Python process (~87 MB) that makes the 512 MB Pi swap.
* Retrain **on the Pi** (`python entrenar_modelo.py`) whenever the model changes;
  a `.pkl` pickled with a different scikit-learn will not load there.
