from flask import Flask, request, render_template, jsonify
import json, time, os

print("🚀 Flask app started (reverted to stable AUTO + manual relay control)")

app = Flask(__name__)

sensor_file = 'sensor.json'
threshold_file = 'thresholds.json'
manual_file = 'manual.json'
refresh_file = 'refresh.txt'

esp_last_seen = 0  # Track ESP32 last ping time

def load(file, default):
    try:
        with open(file) as f:
            return json.load(f)
    except:
        return default

def save(file, data):
    with open(file, 'w') as f:
        json.dump(data, f)

# Ensure required files exist
if not os.path.exists(manual_file):
    default_relays = {"relay1": "auto", "relay2": "auto", "relay3": "auto"}
    save(manual_file, default_relays)

if not os.path.exists(refresh_file):
    with open(refresh_file, 'w') as f:
        f.write(str(time.time()))

latest_data = load(sensor_file, {
    "temperature": 0, "humidity": 0, "soil": 0, "time": "--",
    "relay1": "off", "relay2": "off", "relay3": "off"
})

@app.route('/')
def dashboard():
    return render_template('dashboard.html',
        sensors=load(sensor_file, {}),
        thresholds=load(threshold_file, {}),
        relays=load(manual_file, {})
    )

@app.route('/sensor_data', methods=['POST'])
def sensor_data():
    data = request.get_json(force=True)

    manual_modes = load(manual_file, {})
    existing_state = load(sensor_file, {})

    for key in ["relay1", "relay2", "relay3"]:
        mode = manual_modes.get(key, "auto").lower()
        if mode in ["on", "off"]:
            data[key] = mode  # Manual mode overrides everything
        else:
            data[key] = data.get(key, existing_state.get(key, "off"))  # fallback to ESP-reported state

    save(sensor_file, data)

    global latest_data
    latest_data = data
    return "OK"

@app.route('/sensor_data_live')
def sensor_data_live():
    return jsonify(latest_data)  # ✅ Serve from RAM (no disk lag)

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
    data = request.json
    save(manual_file, data)

    current = load(sensor_file, {})
    for key in ["relay1", "relay2", "relay3"]:
        mode = data.get(key, "").lower()
        if mode in ["on", "off"]:
            current[key] = mode
        elif key in current:
            del current[key]  # Remove stale value when switching to auto
    save(sensor_file, current)

    with open(refresh_file, 'w') as f:
        f.write(str(time.time()))

    return jsonify(status="ok")

@app.route('/refresh.txt')
def refresh_txt():
    try:
        with open(refresh_file) as f:
            return f.read()
    except:
        return str(time.time())

@app.route('/force_refresh')
def force_refresh():
    return "Triggered"

@app.route('/ping', methods=['POST'])
def ping():
    global esp_last_seen
    esp_last_seen = time.time()
    return '', 204

@app.route('/esp_status')
def esp_status():
    if time.time() - esp_last_seen < 30:
        return jsonify({'status': 'online'})
    else:
        return jsonify({'status': 'offline'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
