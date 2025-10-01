from flask import Flask, jsonify
import threading
import time

app = Flask(__name__)

# Başarı bayrağı
success = False

def try_create_vm():
    global success
    while not success:
        # Buraya Oracle Cloud API çağrısı gelecek
        # Eğer VM oluşturulursa success = True
        # Örnek: success = oracle_create_instance()
        print("Deneme yapılıyor...")
        # Simülasyon: 10 saniyede bir dene
        time.sleep(10)
        # Örnek başarılı olursa:
        # success = True

# Arka planda sürekli deneme için thread
threading.Thread(target=try_create_vm, daemon=True).start()

@app.route("/")
def index():
    if success:
        return "✅ VM başarıyla oluşturuldu!"
    else:
        return "⏳ Henüz VM oluşturulamadı, deneme devam ediyor..."

@app.route("/status")
def status():
    return jsonify({"success": success})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
