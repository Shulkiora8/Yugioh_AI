# Yu-Gi-Oh! AI Helper - Asistente Inteligente Multimodal

![Yu-Gi-Oh AI Banner](https://img.shields.io/badge/AI-Agentic-FF004D?style=for-the-badge&logo=openai)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/Frontend-React-61DAFB?style=for-the-badge&logo=react)

Yu-Gi-Oh! AI Helper es un asistente avanzado diseñado para duelistas, que combina visión por computador, recuperación de documentos (RAG) y agentes inteligentes para resolver dudas sobre reglas, identificar cartas físicamente y construir mazos personalizados.

---

## Funcionalidades Principales

### 1. Identificación Visual (Visual RAG)
Utiliza un modelo de visión (**Moondream**) para describir cartas físicas capturadas por la cámara. Esta descripción se procesa mediante una base de datos vectorial en **ChromaDB** para identificar la carta con precisión, incluso si el modelo de lenguaje no conoce el nombre exacto.

### 2. Experto en Reglas (Rule RAG)
El agente tiene acceso directo al manual oficial de Yu-Gi-Oh! (v10). Mediante un sistema de **FAISS**, el asistente recupera los fragmentos más relevantes del PDF para responder preguntas sobre mecánicas complejas (Sincronía, Cadenas, Fases, etc.) evitando alucinaciones.

### 3. Constructor de Mazos Inteligente
A través de herramientas integradas, el asistente puede:
- Buscar cartas en la base de datos local y externa (**YGOPRODeck API**).
- Construir mazos temáticos basados en arquetipos.
- Guardar y persistir mazos en una base de datos **SQLite**, permitiendo su edición posterior en la UI.

---

## Arquitectura del Sistema

El proyecto sigue una arquitectura limpia y modular:

- **Frontend:** React + CSS Vanilla (Premium Design). Interfaz dinámica con visualización de "pensamientos" del agente. Ubicado en la carpeta `/frontend`.
- **Backend:** FastAPI + LangChain. Toda la lógica del servidor, bases de datos e índices RAG se encuentran en la carpeta `/backend`.
- **Agente IA:** Ollama (`qwen2.5:7b`) + `Structured Chat Agent`.

---

## Instalación y Configuración

### Requisitos previos
- [Ollama](https://ollama.ai/) instalado y corriendo.
- Modelos necesarios: `ollama pull qwen2.5:7b` y `ollama pull moondream`.

### Pasos
1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/yugioh-ai-helper.git
   cd Yugioh-AI
   ```
2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Descargar Imágenes de las cartas**
   Ejecuta el archivo `download_cards.py` en la carpeta `backend/`.
   ```bash
   python backend/download_cards.py
   ```
4. **Ejecutar el servidor:**
   ```bash
   cd backend
   python api.py
   ```
5. **Ejecutar el frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## Reflexión Final y Desafíos Técnicos

### 1. Problemas Encontrados y Soluciones
- **Alucinaciones en Reglas:** El modelo tendía a inventar reglas. Se solucionó mediante **RAG estricto**, forzando al agente a citar el manual y limitando la temperatura del modelo a `0.2`.

### 2. Limitaciones de Hardware/Software
- El sistema requiere una GPU con al menos 24GB de VRAM para correr el modelo de 35B con fluidez. Para hardware más modesto, se recomienda cambiar a `qwen2.5:7b`.

### 3. Mejoras a Futuro
- Creacion de seguimiento de usuarios. (Seguidores, amigos)
- Soporte para reglas de formatos alternativos (Speed Duel, Rush Duel).
- Importación y exportación de mazos.
- Mejor manejo de errores.
- Crear una IA que haga duelos con los mazos generados para que el usuario pueda verlos jugar.
- Historial del chat.
---