from flask import Flask, request, render_template, jsonify
import json, time, os

print("🚀 Flask app started (final relay sync & flicker fix)")

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
    print("📥 Incoming POST to /sensor_data")
    print("📄 Raw body:", request.data.decode('utf-8'))

    try:
        data = request.get_json(force=True)
        print("📦 Parsed JSON:", data)

        if not data:
            return "Bad JSON", 400

        # 🔒 Override relay1–3 state based on manual mode if it's on/off (to prevent flicker)
        manual_modes = load(manual_file, {})
        existing_state = load(sensor_file, {})

        for key in ["relay1", "relay2", "relay3"]:
            mode = manual_modes.get(key, "auto").lower()
            if mode in ["on", "off"]:
                data[key] = mode  # lock relay state to manual mode
            else:
                data[key] = existing_state.get(key, "off")  # preserve last known ON/OFF state

        save(sensor_file, data)
        print("💾 Updated sensor.json (trusted relay state)")

        global latest_data
        latest_data = data
        return "OK", 200

    except Exception as e:
        print("❌ Error in /sensor_data:", e)
        return f"Error: {str(e)}", 400

@app.route('/sensor_data_live')
def sensor_data_live():
    return jsonify(load(sensor_file, {}))  # Always read fresh from disk

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

    # ✅ Reflect ON/OFF in sensor.json for dashboard (but not "auto")
    current = load(sensor_file, {})
    for key in ["relay1", "relay2", "relay3"]:
        mode = data.get(key, "").lower()
        if mode in ["on", "off"]:
            current[key] = mode  # show real status
        # else: skip "auto" to preserve last known ON/OFF
    save(sensor_file, current)

    # ✅ Trigger ESP32 update
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
