from flask import Flask, request, jsonify
import joblib

# Load the model
model = joblib.load('decision_tree_model.pkl')

app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict():
    # Get data from the POST request
    data = request.json
    moisture_percentage = data['Moisture_Percentage']
    hour = data['Hour']

    # Predict using the model
    prediction = model.predict([[moisture_percentage, hour]])

    # Return the prediction
    result = 'Regar' if prediction[0] == 1 else 'No regar'
    return jsonify({'prediction': result})

if __name__ == '__main__':
    app.run(debug=True)
