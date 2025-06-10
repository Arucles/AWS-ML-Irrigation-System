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

Before running the post.py script, you need to edit the file with any IDE and edit the line 11 to 15:
CSV_FILE = "soil_moisture_data.csv"
API_ENDPOINT = "http://127.0.0.1:5000/predict"
EMAIL_SENDER = "your_email@gmail.com"
EMAIL_PASSWORD = "your_google_apps_password"  -> This only works with google mails so you need to set app passwords con your google account configuration.
EMAIL_RECIPIENT = "recipient_email@gmail.com"

After you made this changes, save the file and now you can run this script:
python post.py

This will listen to new changes made to the .csv file (you can do it manually or it can be the data sent via sensors)

Now to test the deployed model, edit the .csv file with a new entry (make it so the model predicts with "water" so you recieve the e-mail)
