from flask import Flask, request, render_template, jsonify
import json, time, os

app = Flask(__name__)

sensor_file = 'sensor.json'
threshold_file = 'thresholds.json'
manual_file = 'manual.json'

esp_last_seen = 0  # Track ESP32 last ping time

def load(file, default):  # Load JSON with fallback
    try:
        with open(file) as f:
            return json.load(f)
    except:
        return default

def save(file, data):
    with open(file, 'w') as f:
        json.dump(data, f)

# ✅ Force AUTO mode on startup (or create file if missing)
default_relays = {"relay1": "auto", "relay2": "auto", "relay3": "auto"}
if not os.path.exists(manual_file):
    save(manual_file, default_relays)
else:
    relays = load(manual_file, {})
    # If any relay is missing, reset all to AUTO
    if not all(k in relays for k in ["relay1", "relay2", "relay3"]):
        save(manual_file, default_relays)

latest_data = load(sensor_file, {
    "temperature": 0, "humidity": 0, "soil": 0, "time": "--",
    "relay1": "auto", "relay2": "auto", "relay3": "auto"
})

@app.route('/')
def dashboard():
    return render_template('dashboard.html',
        sensors=load(sensor_file, {}),
        thresholds=load(threshold_file, {}),
        relays=load(manual_file, {})
    )

# ✅ FIXED: Handles JSON properly and avoids 400 error
@app.route('/sensor_data', methods=['POST'])
def sensor_data():
    try:
        data = request.get_json()
        if not data:
            return "Bad JSON", 400
        save(sensor_file, data)
        global latest_data
        latest_data = data
        print("✅ Received from ESP32:", data)
        return "OK", 200
    except Exception as e:
        print("❌ Error in /sensor_data:", e)
        return f"Error: {str(e)}", 400

@app.route('/sensor_data_live')
def sensor_data_live():
    return jsonify(latest_data)

@app.route('/get_thresholds')
def get_thresholds():
    return jsonify(load(threshold_file, {}))

@app.route('/get_relays')
def get_relays():
    relays = load(manual_file, {})
    return jsonify({k: v.lower() for k, v in relays.items()})

@app.route('/update_thresholds', methods=['POST'])
def update_thresholds():
    save(threshold_file, request.form.to_dict())
    return "Updated"

@app.route('/update_relays', methods=['POST'])
def update_relays():
    save(manual_file, request.json)
    return jsonify(status="ok")

@app.route('/force_refresh')
def force_refresh():
    return "Triggered"

# ✅ ESP32 Ping Endpoint
@app.route('/ping', methods=['POST'])
def ping():
    global esp_last_seen
    esp_last_seen = time.time()
    return '', 204

# ✅ Dashboard checks ESP32 status
@app.route('/esp_status')
def esp_status():
    if time.time() - esp_last_seen < 10:
        return jsonify({'status': 'online'})
    else:
        return jsonify({'status': 'offline'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
