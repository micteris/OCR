import os
import re
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pytesseract 
from PIL import Image, ImageTk
import fitz  # PyMuPDF

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

HISTORIAL_FILE = "historial.json"

busqueda_actual = ""
entrada_palabras = None
estado_label = None
imagenes_pdf = []
pagina_actual = 0
img_canvas = None
paginas_con_coincidencias = []

placeholder = "palabra1, palabra2"

# ---------------- GUI ----------------

root = tk.Tk()
root.title("OCR Extractor de Texto desde PDF")
root.geometry("1100x700")

visor_activo = tk.BooleanVar(value=True)

# ---------------- OCR Y PROCESAMIENTO ----------------

def guardar_historial(archivo, palabras, texto):
    historial = cargar_historial()
    historial.append({"archivo": archivo, "palabras": palabras, "texto": texto})
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=4)

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def extraer_texto_thread(archivo, palabras):
    global busqueda_actual, imagenes_pdf, pagina_actual, paginas_con_coincidencias
    root.after(0, mostrar_progreso)
    root.after(0, bloquear_botones)
    busqueda_actual = palabras.strip()
    imagenes_pdf.clear()
    paginas_con_coincidencias.clear()
    pagina_actual = 0

    try:
        doc = fitz.open(archivo)
        resultado = ""
        palabras_busqueda = [p.strip().lower() for p in palabras.split(",") if p.strip()]
        paginas_encontradas = 0

        for i, page in enumerate(doc):
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            imagenes_pdf.append(img)

            texto_pagina = pytesseract.image_to_string(img, lang='spa')
            texto_min = texto_pagina.lower()
            if any(palabra in texto_min for palabra in palabras_busqueda):
                resultado += f"\n--- Página {i + 1} ---\n"
                resultado += texto_pagina + "\n"
                paginas_con_coincidencias.append(i)
                paginas_encontradas += 1

        doc.close()

        def actualizar_texto():
            texto_output.config(state=tk.NORMAL)
            texto_output.delete(1.0, tk.END)
            texto_output.insert(tk.END, resultado)
            aplicar_filtro()
            texto_output.config(state=tk.DISABLED)
            if visor_activo.get():
                if paginas_con_coincidencias:
                    mostrar_pagina(paginas_con_coincidencias[0])
                elif imagenes_pdf:
                    mostrar_pagina(0)
            else:
                ocultar_visor()

        root.after(0, actualizar_texto)
        guardar_historial(archivo, palabras, resultado)

        if paginas_encontradas == 0:
            root.after(0, lambda: estado_label.config(text="No se encontraron coincidencias.", foreground="red"))
            root.after(0, lambda: messagebox.showinfo("Resultado", "No se encontraron coincidencias en el documento."))
        else:
            root.after(0, lambda: estado_label.config(text=f"Se encontraron coincidencias en {paginas_encontradas} página(s).", foreground="green"))

    except Exception as e:
        root.after(0, lambda: messagebox.showerror("Error", f"Ocurrió un problema: {e}"))
    finally:
        root.after(0, desbloquear_botones)
        root.after(0, ocultar_progreso)

# ---------------- HISTORIAL ----------------

def mostrar_historial():
    historial_window = tk.Toplevel(root)
    historial_window.title("Historial de Búsquedas")
    historial_window.geometry("800x400")

    tree = ttk.Treeview(historial_window, columns=("Archivo", "Palabras", "Coincidencias"), show="headings")
    tree.heading("Archivo", text="Archivo Procesado")
    tree.heading("Palabras", text="Palabras Buscadas")
    tree.heading("Coincidencias", text="Coincidencias Encontradas")

    historial = cargar_historial()
    for h in historial:
        conteo = sum(h["texto"].lower().count(p.strip().lower()) for p in h["palabras"].split(",") if p.strip())
        tree.insert("", tk.END, values=(h["archivo"], h["palabras"], conteo))

    tree.pack(fill=tk.BOTH, expand=True)

    def limpiar_y_cerrar():
        respuesta = messagebox.askyesno("Confirmar", "¿Está seguro que desea borrar el historial?")
        if respuesta:
            if os.path.exists(HISTORIAL_FILE):
                os.remove(HISTORIAL_FILE)
                messagebox.showinfo("Éxito", "Historial eliminado correctamente.")
                historial_window.destroy()

    btn_limpiar_historial = tk.Button(historial_window, text="Limpiar Historial", command=limpiar_y_cerrar, bg="#f2dede")
    btn_limpiar_historial.pack(pady=10)

# ---------------- FUNCIONES DE NAVEGACIÓN ----------------

def mostrar_pagina(indice):
    global pagina_actual, img_canvas
    if 0 <= indice < len(imagenes_pdf):
        pagina_actual = indice
        img = imagenes_pdf[indice].resize((400, 520))
        tk_img = ImageTk.PhotoImage(img)
        canvas_pdf.image = tk_img
        canvas_pdf.delete("all")
        canvas_pdf.create_image(0, 0, anchor=tk.NW, image=tk_img)
        label_pagina.config(text=f"Página {pagina_actual + 1} de {len(imagenes_pdf)}")

def ocultar_visor():
    canvas_pdf.delete("all")
    label_pagina.config(text="")

def toggle_visor():
    if visor_activo.get():
        mostrar_pagina(pagina_actual)
    else:
        ocultar_visor()

def pagina_anterior():
    if pagina_actual > 0:
        mostrar_pagina(pagina_actual - 1)

def pagina_siguiente():
    if pagina_actual < len(imagenes_pdf) - 1:
        mostrar_pagina(pagina_actual + 1)

# ---------------- PROCESAR IMAGEN ----------------

def procesar_imagen():
    archivo_img = filedialog.askopenfilename(filetypes=[("Archivos de imagen", "*.png;*.jpg;*.jpeg;*.bmp")])
    if not archivo_img:
        return

    palabras = entrada_palabras.get().strip()
    if palabras == "" or palabras == placeholder:
        messagebox.showwarning("Advertencia", "Por favor, ingrese palabras clave antes de continuar.")
        return

    def ocr_imagen():
        root.after(0, mostrar_progreso)
        root.after(0, bloquear_botones)
        try:
            img = Image.open(archivo_img)
            texto = pytesseract.image_to_string(img, lang='spa')
            palabras_busqueda = [p.strip().lower() for p in palabras.split(",") if p.strip()]
            coincidencias = sum(texto.lower().count(p) for p in palabras_busqueda)

            texto_output.config(state=tk.NORMAL)
            texto_output.delete(1.0, tk.END)
            texto_output.insert(tk.END, texto)
            aplicar_filtro()
            texto_output.config(state=tk.DISABLED)

            if coincidencias == 0:
                estado_label.config(text="No se encontraron coincidencias.", foreground="red")
                messagebox.showinfo("Resultado", "No se encontraron coincidencias en la imagen.")
            else:
                estado_label.config(text=f"Se encontraron {coincidencias} coincidencia(s).", foreground="green")
                messagebox.showinfo("Resultado", f"¡Coincidencias encontradas en la imagen!")

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un problema: {e}")
        finally:
            desbloquear_botones()
            ocultar_progreso()

    threading.Thread(target=ocr_imagen, daemon=True).start()

# ---------------- CONTINUACIÓN DE GUI ----------------

frame_top = tk.Frame(root)
frame_top.pack(pady=5)

label_palabras = tk.Label(frame_top, text="Palabras clave a buscar (separadas por coma):")
label_palabras.grid(row=0, column=0, columnspan=3)

entrada_palabras = tk.Entry(frame_top, width=50, fg='gray')
entrada_palabras.grid(row=1, column=0)
entrada_palabras.insert(0, placeholder)

btn_clear_entry = tk.Button(frame_top, text="✖", command=lambda: limpiar_entry())
btn_clear_entry.grid(row=1, column=1, padx=(5, 0))

chk_visor = tk.Checkbutton(frame_top, text="Mostrar visor PDF", variable=visor_activo, command=toggle_visor)
chk_visor.grid(row=1, column=2, padx=10)

frame_botones = tk.Frame(root)
frame_botones.pack(pady=5)

btn_historial = tk.Button(root, text="Ver Historial", command=mostrar_historial)
btn_historial.pack(pady=5)

estado_label = tk.Label(root, text="", font=("Arial", 10))
estado_label.pack(pady=2)

progreso = ttk.Label(root, text="Procesando...", font=("Arial", 12))
progreso.place_forget()

frame_izquierdo = tk.Frame(root)
frame_izquierdo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

frame_derecho = tk.Frame(root)
frame_derecho.pack(side=tk.RIGHT, fill=tk.Y, padx=10)

texto_output = tk.Text(frame_izquierdo, wrap=tk.WORD, height=30, state=tk.DISABLED)
texto_output.pack(fill=tk.BOTH, expand=True)

canvas_pdf = tk.Canvas(frame_derecho, width=400, height=520, bg="#f0f0f0")
canvas_pdf.pack()

label_pagina = tk.Label(frame_derecho, text="Página 0 de 0")
label_pagina.pack(pady=5)

frame_nav = tk.Frame(frame_derecho)
frame_nav.pack()

btn_prev = tk.Button(frame_nav, text="<< Anterior", command=pagina_anterior)
btn_prev.pack(side=tk.LEFT, padx=5)

btn_next = tk.Button(frame_nav, text="Siguiente >>", command=pagina_siguiente)
btn_next.pack(side=tk.LEFT, padx=5)

# ---------------- BOTONES PRINCIPALES ----------------

archivo_seleccionado = ""

def seleccionar_pdf():
    global archivo_seleccionado
    archivo_seleccionado = filedialog.askopenfilename(filetypes=[("Archivos PDF", "*.pdf")])
    if archivo_seleccionado:
        estado_label.config(text=f"Archivo seleccionado: {os.path.basename(archivo_seleccionado)}", foreground="blue")

def procesar_pdf():
    global archivo_seleccionado
    palabras = entrada_palabras.get().strip()
    if not archivo_seleccionado:
        messagebox.showwarning("Advertencia", "Por favor, seleccione un archivo PDF.")
        return
    if palabras == "" or palabras == placeholder:
        messagebox.showwarning("Advertencia", "Por favor, ingrese palabras clave antes de continuar.")
        return

    entrada_palabras.config(fg='black')
    threading.Thread(target=extraer_texto_thread, args=(archivo_seleccionado, palabras), daemon=True).start()

def mostrar_progreso():
    progreso.place(relx=0.5, rely=0.08, anchor=tk.CENTER)

def ocultar_progreso():
    progreso.place_forget()

def bloquear_botones():
    btn_cargar.config(state=tk.DISABLED)
    btn_procesar.config(state=tk.DISABLED)
    btn_prev.config(state=tk.DISABLED)
    btn_next.config(state=tk.DISABLED)
    btn_limpiar.config(state=tk.DISABLED)
    btn_clear_entry.config(state=tk.DISABLED)
    btn_procesar_imagen.config(state=tk.DISABLED)

def desbloquear_botones():
    btn_cargar.config(state=tk.NORMAL)
    btn_procesar.config(state=tk.NORMAL)
    btn_prev.config(state=tk.NORMAL)
    btn_next.config(state=tk.NORMAL)
    btn_limpiar.config(state=tk.NORMAL)
    btn_clear_entry.config(state=tk.NORMAL)
    btn_procesar_imagen.config(state=tk.NORMAL)

def limpiar_entry():
    entrada_palabras.delete(0, tk.END)
    entrada_palabras.insert(0, placeholder)
    entrada_palabras.config(fg='gray')
    estado_label.config(text="")
    texto_output.config(state=tk.NORMAL)
    texto_output.delete(1.0, tk.END)
    texto_output.config(state=tk.DISABLED)
    canvas_pdf.delete("all")
    label_pagina.config(text="Página 0 de 0")
    global archivo_seleccionado, imagenes_pdf
    archivo_seleccionado = ""
    imagenes_pdf.clear()

entrada_palabras.bind('<FocusIn>', lambda e: (entrada_palabras.delete(0, tk.END), entrada_palabras.config(fg='black')) if entrada_palabras.get() == placeholder else None)
entrada_palabras.bind('<FocusOut>', lambda e: (entrada_palabras.insert(0, placeholder), entrada_palabras.config(fg='gray')) if not entrada_palabras.get().strip() else entrada_palabras.config(fg='black'))

btn_cargar = tk.Button(frame_botones, text="Seleccionar PDF", command=seleccionar_pdf)
btn_cargar.pack(side=tk.LEFT, padx=5)

btn_procesar = tk.Button(frame_botones, text="Procesar Documento", command=procesar_pdf)
btn_procesar.pack(side=tk.LEFT, padx=5)

btn_procesar_imagen = tk.Button(frame_botones, text="Procesar Imagen", command=procesar_imagen)
btn_procesar_imagen.pack(side=tk.LEFT, padx=5)

btn_limpiar = tk.Button(frame_botones, text="Limpiar Ventana", command=lambda: texto_output.config(state=tk.NORMAL) or texto_output.delete(1.0, tk.END) or texto_output.config(state=tk.DISABLED))
btn_limpiar.pack(side=tk.LEFT, padx=5)

root.mainloop()