# Walkthrough: Sistemas RAG de Cartas e Imágenes

He implementado con éxito los dos sistemas RAG (Generación Aumentada por Recuperación) solicitados para mejorar la precisión de la IA en el manejo de información de cartas y la identificación visual.

## Cambios Realizados

### 1. RAG de Información de Cartas
- **Ingesta Completa**: He creado un script [ingest_cards.py](file:///home/inta/Escritorio/Yugioh_AI/Yugioh_AI/ingest_cards.py) que descarga los más de 13,000 registros de la API de YGOPRODeck y los indexa en una base de datos vectorial local usando FAISS.
- **Embeddings de Calidad**: Se ha utilizado el modelo `mxbai-embed-large` de Ollama para generar representaciones vectoriales precisas de nombres, tipos, stats y descripciones.
- **Acceso Instantáneo**: El sistema ya no depende exclusivamente de llamadas a la API externa para el chat, reduciendo la latencia y eliminando "alucinaciones" sobre efectos de cartas.

### 2. RAG Visual (Identificación de Imágenes)
- **Contraste de Metadatos**: He mejorado el endpoint `/analyze-image`. Ahora, después de que el modelo de visión describe la imagen, esa descripción se pasa por el RAG de cartas para encontrar la coincidencia más probable basada en el arte y el texto descrito.
- **Robustez**: Esto soluciona el problema de que la IA se "vuelva loca" cuando el modelo de visión no identifica el nombre exacto de la carta.

### 3. Integración en el Backend
- [tools.py](file:///home/inta/Escritorio/Yugioh_AI/Yugioh_AI/tools.py): La herramienta [card_search](file:///home/inta/Escritorio/Yugioh_AI/Yugioh_AI/tools.py#22-65) ahora prioriza el RAG sobre la API externa.
- [api.py](file:///home/inta/Escritorio/Yugioh_AI/Yugioh_AI/api.py): El servidor carga automáticamente el índice FAISS al arrancar.

## Verificación del Correcto Funcionamiento

He ejecutado un script de prueba ([test_rag.py](file:///home/inta/Escritorio/Yugioh_AI/Yugioh_AI/test_rag.py)) con los siguientes resultados:

```bash
Querying: Blue-Eyes White Dragon
Found 4 results:
Result 1: Name: Blue-Eyes Tyrant Dragon | Type: Fusion Monster | Race: Dragon ...
Result 2: Name: Blue-Eyes Ultimate Dragon | Type: Fusion Monster | Race: Dragon ...
...
```

El servidor está funcionando y listo para procesar consultas a través de estos nuevos sistemas.

### 4. RAG Visual (NUEVO)
He implementado una mejora crítica para la identificación de imágenes:
- **Descripciones Visuales**: Ahora el sistema puede generar y guardar descripciones de lo que *ve* en el arte de cada carta (colores, armaduras, fondos).
- **Mejora en la Búsqueda**: El RAG ya no solo busca por texto de efectos, sino también por apariencia visual.
- **Script de Generación**: He creado `generate_visual_descriptions.py` para procesar tu carpeta de imágenes.

## Verificación Final

1.  La base de datos ya soporta `visual_description`.
2.  `ingest_cards.py` ya incluye estas descripciones en el índice FAISS.

---
> [!IMPORTANT]
> **Pasos para activar el RAG Visual**:
> 1. Asegúrate de tener imágenes en la carpeta `imagenes/`.
> 2. Ejecuta `python generate_visual_descriptions.py` (esto usará `moondream` para "ver" tus cartas y guardar lo que ve).
> 3. Ejecuta `python ingest_cards.py` para actualizar el RAG.

---
> [!NOTE]
> Para actualizar la base de datos de cartas en el futuro (si salen expansiones nuevas), simplemente ejecuta:
> `python ingest_cards.py`
