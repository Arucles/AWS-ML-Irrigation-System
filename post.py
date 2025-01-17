import time
import pandas as pd
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
CSV_FILE = "soil_moisture_data.csv"
API_ENDPOINT = "http://127.0.0.1:5000/predict"
EMAIL_SENDER = ""
EMAIL_PASSWORD = ""
EMAIL_RECIPIENT = ""

# Email-sending function
def send_email(prediction, moisture, hour):
    subject = "Plant Watering Alert"
    body = (
        f"The prediction is '{prediction}'.\n"
        f"Moisture Level: {moisture}%\n"
        f"Hour: {hour}\n"
        "It's time to water your plants!"
    )

    # Set up the email message
    message = MIMEMultipart()
    message["From"] = EMAIL_SENDER
    message["To"] = EMAIL_RECIPIENT
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, message.as_string())
            print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# File monitoring handler
class CSVHandler(FileSystemEventHandler):
    def __init__(self, csv_file, api_endpoint):
        self.csv_file = csv_file
        self.api_endpoint = api_endpoint
        self.last_row = None  # Store the last processed row

    def on_modified(self, event):
        if event.src_path.endswith(self.csv_file):
            try:
                # Read the updated CSV file
                data = pd.read_csv(self.csv_file)

                # Get the last row
                new_row = data.iloc[-1]

                # Check if it's already processed
                if self.last_row is None or not new_row.equals(self.last_row):
                    self.last_row = new_row

                    # Extract features for the POST request
                    payload = {
                        "Moisture_Percentage": new_row["Moisture_Percentage"],
                        "Hour": pd.to_datetime(new_row["Time"]).hour
                    }

                    # Send the POST request
                    response = requests.post(self.api_endpoint, json=payload)
                    response_data = response.json()
                    print(f"Sent POST request: {payload}")
                    print(f"Response: {response_data}")

                    # Check the prediction and send an email if it's "Water"
                    if response_data.get("prediction") == "Regar":
                        send_email(
                            prediction="Regar",
                            moisture=payload["Moisture_Percentage"],
                            hour=payload["Hour"]
                        )
            except Exception as e:
                print(f"Error processing file: {e}")

if __name__ == "__main__":
    event_handler = CSVHandler(CSV_FILE, API_ENDPOINT)
    observer = Observer()
    observer.schedule(event_handler, ".", recursive=False)  # Monitor current directory
    observer.start()

    print(f"Monitoring {CSV_FILE} for changes...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
