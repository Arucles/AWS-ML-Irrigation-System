# AWS-ML-Irrigation-System
Final project for AWS Re/Start course. Consists of an automated plant irrigation system that uses sensors to collect soil moisture data, then feed a Decision Tree machine learning model to classify whether the plant needs watering or not.

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
