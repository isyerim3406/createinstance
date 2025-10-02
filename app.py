import os
from flask import Flask, jsonify
import oci
# Diğer importlar: tempfile, base64, vb.

app = Flask(__name__)

# VM başlatma denemesini yapan fonksiyon
def launch_instance_attempt():
    # ... (launch_instance fonksiyonunuzun önceki hali)
    # Başarılı olursa {status: success}, hata olursa {status: error} döndürmeye devam etmeli.
    
    # Sadece launch_instance fonksiyonunun adını launch_instance_attempt olarak değiştirelim
    # ve tek deneme yapmasını sağlayalım.
    
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)
        
        # ... (shape_config, instance_details, vb. önceki kodlar buraya gelir)
        
        response = compute_client.launch_instance(instance_details)
        
        return {
            "status": "success",
            "message": f"VM Başarıyla Başlatıldı! ID: {response.data.id}",
            "instance_id": response.data.id
        }

    except oci.exceptions.ServiceError as e:
        # Kapasite Hatası alınca, bunu açıkça belirt
        if "Out of host capacity" in e.message:
            return {
                "status": "error",
                "error_type": "CapacityError",
                "message": f"Out of host capacity. Tekrar Deneyin. Son deneme: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            }
        # Diğer OCI hataları
        return {
            "status": "error",
            "error_type": "OCI Service Error",
            "message": e.message,
            "code": e.code
        }
    except Exception as e:
        # Yapılandırma hataları
        return {"status": "error", "error_type": type(e).__name__, "message": str(e)}

# Ana endpoint
@app.route("/")
def home():
    result = launch_instance_attempt()
    # Kapasite hatası bile olsa, HTTP 200 döndürmeliyiz ki harici servis panik yapmasın.
    # Ancak hata kodunu da belirtmeliyiz.
    http_status = 200 if result["status"] == "success" else 400
    
    if result["status"] == "success":
        # Başarılı olursa, artık durması gerektiğini belirtiriz.
        print("VM Başlatıldı. Harici Tetikleyici Durdurulmalı!")
    
    return jsonify(result), http_status

# ... (Diğer tüm yollarınız ve get_signer fonksiyonunuz olduğu gibi kalır)
# ...

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
