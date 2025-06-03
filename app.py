from flask import Flask, request, render_template, jsonify
import json, time, os

print("🚀 Flask app started (updated with refresh logic)")

app = Flask(__name__)

sensor_file = 'sensor.json'
threshold_file = 'thresholds.json'
manual_file = 'manual.json'
refresh_file = 'refresh.txt'

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

# ✅ Ensure required files exist
if not os.path.exists(manual_file):
    default_relays = {"relay1": "auto", "relay2": "auto", "relay3": "auto"}
    save(manual_file, default_relays)

if not os.path.exists(refresh_file):
    with open(refresh_file, 'w') as f:
        f.write(str(time.time()))

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

@app.route('/sensor_data', methods=['POST'])
def sensor_data():
    print("📥 Incoming POST to /sensor_data")
    print("🔎 Headers:", dict(request.headers))
    print("📄 Raw body:", request.data.decode('utf-8'))

    try:
        data = request.get_json(force=True)
        print("📦 Parsed JSON:", data)

        if not data:
            print("❌ No data parsed from JSON")
            return "Bad JSON", 400

        try:
            save(sensor_file, data)
            print("💾 Saved to sensor.json")
        except Exception as save_error:
            print("❌ Failed to save sensor.json:", save_error)

        global latest_data
        latest_data = data
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
    data = request.json
    save(manual_file, data)

    # ✅ Update refresh.txt to trigger ESP32 fetch
    with open(refresh_file, 'w') as f:
        f.write(str(time.time()))

    return jsonify(status="ok")

@app.route('/refresh.txt')
def refresh_txt():
    try:
        with open(refresh_file) as f:
            return f.read()
    except:
        return str(time.time())  # fallback

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
