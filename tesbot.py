import logging
from decimal import Decimal, ROUND_HALF_UP
import re
import csv
import io
import os
from telegram import Update, InputFile
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext
)

# ENVIROMENT VARIABLE #
TOKEN = os.getenv("TOKEN")
CLCAP = os.getenv("CLCAP") 
NBCAP = os.getenv("NBCAP") 
CLCOM = os.getenv("CLCOM")
NBCOM = os.getenv("NBCOM")


us = {}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validar_clave(clave):
    patron = r"^\d{4}-\d{3}-[A-Za-z]-\d{2}$"
    return re.match(patron, clave) is not None

def dividir_montos(total):
    total = Decimal(total)
    MINIMO = Decimal("250000")
    MAXIMO = Decimal("349999")

    if total < MINIMO:
        return [total]

    for n in range(2, 11):
        monto = (total / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if MINIMO <= monto <= MAXIMO:
            partes = [monto] * n
            diferencia = total - sum(partes)

            # Ajustar
            if diferencia != 0:
                partes[0] += diferencia

            if all(MINIMO <= p <= MAXIMO for p in partes):
                return partes

    return [total]

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    us[user_id] = {"estado": "clave"}
    update.message.reply_text(
        "Bienvenido.\n\nPor favor ingresa la clave con formato:\n*1234-567-A-89*",
        parse_mode="Markdown"
    )

def recibir_mensaje(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    msj = update.message.text.strip()

    if user_id not in us:
        update.message.reply_text("Escribe /start para comenzar.")
        return

    estado = us[user_id]["estado"]

    if estado == "clave":
        if not validar_clave(msj):
            update.message.reply_text("❌ Formato incorrecto. Ejemplo: 1234-567-A-89")
            return
        us[user_id]["clave"] = msj
        us[user_id]["estado"] = "capital"
        update.message.reply_text("✔ Clave válida.\n\nAhora ingresa el *capital*.", parse_mode="Markdown")
        return

    if estado == "capital":
        try:
            capital = Decimal(msj.replace(",", ""))
        except:
            update.message.reply_text("❌ Ingresa un número válido.")
            return

        if capital <= 0:
            update.message.reply_text("❌ El capital debe ser mayor a 0.")
            return

        us[user_id]["capital"] = capital
        us[user_id]["estado"] = "comision"
        update.message.reply_text("✔ Capital recibido.\n\nAhora ingresa la *comisión*:", parse_mode="Markdown")
        return

    if estado == "comision":
        try:
            comision = Decimal(msj.replace(",", ""))
        except:
            update.message.reply_text("❌ Ingresa una comisión válida.")
            return

        us[user_id]["comision"] = comision

        generar_csv_memoria(update, context, user_id)
        us.pop(user_id, None)
        return

def generar_csv_memoria(update: Update, context: CallbackContext, user_id):
    datos = us[user_id]
    clave = datos["clave"]
    capital = datos["capital"]
    comision = datos["comision"]

    partes_capital = dividir_montos(capital)

    plantilla_csv = "DISPERSION FONDEADORA.csv"

    if not os.path.exists(plantilla_csv):
        update.message.reply_text("❌ La plantilla CSV no se encuentra en el proyecto.")
        return

    with open(plantilla_csv, newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        header = reader[0]
        filas = reader[1:]

    nueva_filas = filas.copy()
    fila_vacia = [""] * len(header)

    for p in partes_capital:
        fila = fila_vacia.copy()
        fila[0] = CLCAP
        fila[1] = NBCAP
        fila[2] = str(float(p))
        fila[3] = clave
        nueva_filas.append(fila)

    fila = fila_vacia.copy()
    fila[0] = CLCOM
    fila[1] = NBCOM
    fila[2] = str(float(comision))
    fila[3] = clave
    nueva_filas.append(fila)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(nueva_filas)
    output.seek(0)

    update.message.reply_document(
        document=InputFile(output, filename=f"Layout {clave}.csv"),
        caption="📄 Archivo CSV generado exitosamente."
    )
    output.close()

# -------- MAIN -------- #
def main():
    print("BOT INICIADO…")
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, recibir_mensaje))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()