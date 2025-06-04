from flask import Flask, request, render_template, jsonify
import json, time, os

print("🚀 Flask app started (stable synced version)")

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
    save(manual_file, {"relay1": "auto", "relay2": "auto", "relay3": "auto"})

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
    try:
        data = request.get_json(force=True)
        manual_modes = load(manual_file, {})
        current_state = load(sensor_file, {})

        # ✅ Only update relay values if in auto
        for key in ["relay1", "relay2", "relay3"]:
            mode = manual_modes.get(key, "auto").lower()
            incoming = data.get(key)

            if mode == "auto":
                if incoming in ["on", "off"]:
                    data[key] = incoming
                else:
                    data[key] = current_state.get(key, "off")
            else:
                data[key] = mode  # force manual override

        save(sensor_file, data)
        global latest_data
        latest_data = data
        return "OK", 200

    except Exception as e:
        print("❌ Error:", e)
        return f"Error: {str(e)}", 400

@app.route('/sensor_data_live')
def sensor_data_live():
    # ✅ Always serve the latest relay values based on manual.json
    data = latest_data.copy()
    manual = load(manual_file, {})
    for key in ["relay1", "relay2", "relay3"]:
        mode = manual.get(key, "auto").lower()
        if mode in ["on", "off"]:
            data[key] = mode
    return jsonify(data)

@app.route('/get_relays')
def get_relays():
    return jsonify(load(manual_file, {}))

@app.route('/get_thresholds')
def get_thresholds():
    return jsonify(load(threshold_file, {}))

@app.route('/update_thresholds', methods=['POST'])
def update_thresholds():
    save(threshold_file, request.form.to_dict())
    return "Updated"

@app.route('/update_relays', methods=['POST'])
def update_relays():
    data = request.json
    save(manual_file, data)

    # ✅ Update sensor.json immediately for visual feedback
    state = load(sensor_file, {})
    for key in ["relay1", "relay2", "relay3"]:
        mode = data.get(key, "auto").lower()
        if mode in ["on", "off"]:
            state[key] = mode
    save(sensor_file, state)

    # ✅ Update refresh.txt to trigger ESP32
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
    return jsonify({'status': 'online' if time.time() - esp_last_seen < 30 else 'offline'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
