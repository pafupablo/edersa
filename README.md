# EdERSA · Explorador de usuarios

Aplicación Streamlit de lectura que relaciona las cuatro planillas de la carpeta Estructural, las soluciones territoriales y el formulario de producción con su tabla de personas. Incluye caracterización de hogares, panorama, fichas, comparación de consumos y revisión de vínculos pendientes.

## Abrir la versión local

En Windows, abrir `INICIAR.cmd`. La primera ejecución en otro equipo requiere Python 3.12 e Internet para instalar dependencias. En este equipo ya se preparó el entorno en la carpeta superior `.venv-streamlit`.

Alternativamente, desde esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

La copia en `data/` sirve para revisar la aplicación con los datos leídos el 17/11/2026. Se muestra explícitamente como **Copia local**; no recibe cambios de Drive. Es privada, está ignorada por Git y no se incluye en el paquete de código para publicar. La consulta a Sheets online está implementada pero requiere configurar las credenciales siguientes.

## Conectar los Sheets privados

1. Crear o seleccionar un proyecto en Google Cloud y habilitar **Google Sheets API** y **Google Drive API**. Esta solución no utiliza BigQuery ni necesita recursos de pago.
2. Crear una cuenta de servicio para lectura y una clave JSON. Guardar esa clave de forma privada. No incluirla en GitHub ni enviarla por chat.
3. Compartir los cuatro Sheets, el Excel de soluciones y Formulario EdERSA como **Lector** con el `client_email` de esa cuenta. No hace falta hacer públicos los archivos ni convertir el Excel.
4. Usar `.streamlit/secrets.toml.example` como guía y completar `[gcp_service_account]` con los datos de la clave. En local, guardarlo como `.streamlit/secrets.toml`. Online, pegarlo directamente en **Settings → Secrets** de Streamlit.
5. Abrir la aplicación y elegir **Google Sheets + Drive**. Verificar los recuentos en **Fuentes y calidad**.

Los IDs, pestañas y columnas están en `sources.json`, ya configurados. La aplicación usa `spreadsheets.readonly` para las planillas nativas y `drive.readonly` para descargar el Excel. Solo tiene acceso a los archivos compartidos con la cuenta de servicio; no escribe ni cambia permisos. Las credenciales que usa Codex para revisar Drive no se transfieren a Streamlit.

Se cachea cada lectura durante 5 minutos. **Actualizar datos**, al pie de la barra lateral, fuerza la lectura de las fuentes. No es sincronización continua en segundo plano. Si falla el acceso online, se informa el error y no se sustituye silenciosamente por la copia local.

Guía oficial: https://docs.streamlit.io/develop/tutorials/databases/private-gsheet

## Publicar gratis en Streamlit Community Cloud

1. Crear un repositorio **privado** en GitHub. Subir el contenido del paquete de código, conservando `.streamlit/config.toml`. No subir `data/`, entornos virtuales ni `secrets.toml`.
2. Entrar en https://share.streamlit.io/ y vincular GitHub. La cuenta y las autorizaciones se completan desde el navegador del titular.
3. Crear la aplicación desde ese repositorio: archivo principal `app.py`, Python 3.12.
4. Configurar la sección Secrets con la cuenta de servicio antes del primer arranque.
5. Mantener la aplicación privada y autorizar solo a los lectores del equipo. Verificar el acceso desde otra cuenta antes de compartir el enlace.

Community Cloud permite una aplicación privada por espacio y puede ponerla en reposo después de inactividad. El alojamiento tiene recursos limitados. Sheets también aplica cuotas: la caché evita repetir lecturas grandes por cada filtro.

La publicación y la conexión en vivo requieren completar los pasos de cuenta y credenciales. La revisión local usa los datos reales; no equivale a una publicación online.

## Modelo y significado

## Caracterización de hogares

Fuente: [Formulario EdERSA de producción](https://docs.google.com/spreadsheets/d/15ErlZXsZgrmHpKdeWLPDsgcI9A5AhqBjrUCFWmgAm5Q/edit). Se leen Relevamiento Producción y grupo_personas. La selección de columnas para la aplicación excluye nombres, DNI, teléfonos, correos, fotografías, información de deuda e ingresos. El código admite columnas nuevas sin importar automáticamente campos personales.

La sección tiene filtros propios por departamento, localidad, barrio y Tipo PASE, con manzana/lote y vínculo al padrón como opciones adicionales. Incluye hogares sin NIS para conservar la cobertura territorial. Se distinguen registros de campo, encuestas completas y encuestas residenciales de vivienda ocupada. La revisión del 17/11/2026 contiene 1.465 registros, 1.024 completas y 1.020 residenciales, con 3.258 personas declaradas.

El relato se organiza en composición del hogar, vivienda y materiales, climatización/cocina, condiciones eléctricas y cobertura. Incluye treemap territorial, distribución de tamaños con cantidades y porcentajes, composición mayores/menores, pirámide de edad/género, anillos de materiales, matriz de estado general/filtraciones y cantidad de situaciones eléctricas por vivienda. Cada gráfico muestra su base.

Los indicadores destacados de Sí/No usan respuestas definidas. Las barras apiladas de equipamiento y energía muestran Sí, No y Sin dato/NSNC sobre el total seleccionado, con la tasa entre respuestas definidas disponible en el cursor. No se convierten faltantes en ceros. Las preguntas múltiples de energía pueden sumar más de 100%.

El campo personas_menores_edad_cantidad contiene respuestas sobre asistencia escolar. Los menores se derivan como total menos mayores solo cuando ambos datos son válidos y coherentes. El género y las edades de grupo_personas se presentan como cobertura parcial; las personas se vinculan por UUID de encuesta, nunca por posición de fila.

La unidad principal es la encuesta residencial, no una vivienda física única garantizada: se conservan ubicaciones repetidas y se muestran para revisar. No se calcula NBI ni una clasificación estructural no definida por el formulario. **Personas por ambiente** usa personas_cantidad / ambientes_totales. **Hacinamiento crítico** indica más de tres personas por ambiente, según el criterio operativo solicitado. Cero ambientes o denominador ausente producen dato no disponible. Los cortes menores a 100 pertenecen al análisis de consumos y no excluyen encuestas.

El vínculo con el padrón usa NIS exacto y RENABAP cuando está disponible. Un NIS ambiguo o un barrio contradictorio no se asigna. Las etiquetas territoriales codificadas se normalizan; si el barrio no puede resolverse de forma única, se conserva como ubicación sin confirmar. Las fichas de usuarios con vínculo muestran la encuesta residencial más reciente y advierten si hay más de una.

## Padrón y consumos

- Universo: **Usuarios general**, 9.527 filas en la revisión inicial. La clave es `Usua_ID`.
- Consumos y GPS se vinculan por `Usua_ID`. **No se cruza por NIS**, porque se repite en algunos usuarios.
- `id_renabap por poligono` se relaciona con `ID Renabap` en Barrios.
- `Subt_coord` contiene longitud y `Sibt_coord` latitud en la fuente actual.
- La etiqueta fuente `oct-24` es el mes facturado: el período consumido mostrado es agosto–septiembre de 2024. `feb-26` se muestra como diciembre de 2025–enero de 2026. Se conserva el mes facturado en `periodo_facturado` y la etiqueta original en `bimestre_fuente`; `periodo` es el inicio del período consumido, dos meses antes. Se lee el texto formateado, no el serial subyacente de Sheets.
- Registro sin gas vacío: **Sin información**. No implica acceso a gas.
- PASE y Tipo PASE son atributos del barrio. Tipo PASE es filtro principal; gas se encuentra en Más filtros. Programa se agrupa en **300 / No 300** y conserva su código original en la base. Los faltantes no se clasifican como No 300. No hay filtro GPS ni coordenadas en las fichas.
- No se confirmó la unidad física de la columna Consumo; se evita etiquetar los valores como kWh hasta confirmarla.
- La ficha representa un **usuario/suministro**. Todavía no existe un padrón que confirme su equivalencia con hogares o viviendas.
- La fuente territorial agrega soluciones, fechas y estados individuales. Se leen solo A:L de la pestaña solicitada; no se importan emails, teléfonos, DNI, deudas ni sus tablas auxiliares. Los campos posteriores de caracterización de vivienda no se integran en esta versión.

## Intervenciones territoriales

Fuente: https://docs.google.com/spreadsheets/d/1x-KtYXZDIbylgitLAVtcNcFkib5NGajz/edit?gid=1014042561. Es un Excel en Drive; se descarga y lee sin modificarlo ni convertirlo.

Cada fila con SOLUCIÓN/PROPUESTA es un registro. Puede contener más de una solución y no equivale necesariamente a una obra. Las filas sin solución se conservan como incidencias. Solo un ‘sí’ explícito en Ejecutada se contabiliza como ejecución. ‘No’, ‘se niega’, ‘Resolvieron’ y vacío se conservan como estados diferentes. Las fechas no interpretables quedan como notas, sin inventar una fecha.

El vínculo usa NIS exacto y los componentes Persona/Cuenta del Usua_ID, retirando ceros de relleno para compararlos. El campo sum puede aportar Persona-Cuenta cuando faltan componentes. Se normalizan acentos, mayúsculas, prefijo Barrio y equivalencias 2/Dos, 4/Cuatro, 10/Diez; en Los Sauces se admite el sufijo de localidad. No se usa coincidencia difusa de nombres ni se asigna por barrio solamente.

NIS y Persona/Cuenta incompatibles quedan en Conflicto. Un barrio diferente, un NIS informado que no aparece o una corroboración insuficiente quedan como Probable, sin asignación. Más de un candidato sin resolución queda Ambiguo. Los casos sin identificadores o ausentes del padrón permanecen visibles para revisar. No se agregan usuarios al padrón a partir de soluciones.

Solo los vínculos Confirmados alimentan la ficha, el filtro y la comparación por ejecución. Los duplicados exactos se conservan pero se cuentan una vez. La aplicación muestra el criterio, los candidatos y la fila de origen. No tiene un mecanismo de confirmación manual: corregir la fuente y actualizar permite recalcular los vínculos.

El grupo ‘Con ejecución registrada’ considera cualquier fecha; no implica que la intervención preceda al consumo seleccionado. ‘Sin ejecución registrada’ no acredita ausencia de intervención. No se usa esta comparación como estimación causal.

## Integridad y faltantes

Claves maestras vacías o repetidas detienen la consulta. Mediciones de consumo con valor negativo/no numérico, período no interpretable o clave usuario-período repetida quedan excluidas y visibles en calidad. No se suman duplicados. Los consumos sin usuario también quedan fuera del universo. Un consumo cero válido se conserva; un dato faltante nunca se imputa como cero.

Todas las estadísticas de consumo usan únicamente mediciones de consumo **mayores o iguales a 100**, incluidos medias, medianas, percentiles, desvíos, totales y cantidad de usuarios con medición de consumo apta para estadísticas. El corte es por medición de consumo: un usuario puede participar en un período y quedar excluido en otro. Los usuarios siguen en el padrón y los valores menores a 100 se conservan en la ficha, identificados como excluidos de estadísticas.

La mediana es la medida principal. La evolución separa **consumo** (mediana azul, media amarilla y banda P25–P75) de **cantidad de usuarios** (barras en un panel inferior con su propio eje). El cursor informa variación porcentual de la mediana y cobertura de usuarios; ya no incluye desvío estándar. La descarga CSV distingue explícitamente columnas de consumo y de usuarios e incluye los faltantes y valores menores a 100 excluidos. La composición observada puede cambiar entre períodos. Un período sin dato aparece como un hueco.

## Barrios: cobertura e incidencia

El gráfico compara los mismos barrios en filas compartidas: a la izquierda, los usuarios registrados desglosados por tipo de consumo; a la derecha, usuarios registrados y viviendas estimadas sin servicio. Ambos paneles van de 0 a 100%: consumo sobre usuarios registrados y servicio sobre viviendas estimadas, usadas como aproximación de familias. Al final de cada fila se muestra el total de familias estimadas. Las etiquetas interiores muestran cantidades. La cobertura se limita al 100% cuando los usuarios superan la estimación; se conserva el conteo real en las etiquetas. Se puede ordenar por casos a revisar, incidencia, faltante de servicio estimado o usuarios registrados. Los botones Primero/Anterior/Siguiente/Último recorren todos los barrios de a 15 y permiten saltar al inicio o al final; al cambiar filtros u orden se vuelve a la primera página. Las etiquetas muestran Nombre del barrio (ID) y debajo la localidad. El faltante de servicio es una estimación, no un relevamiento directo.

La sección incluye todos los barrios filtrados territorialmente, también los que no tienen usuarios registrados. Caracterización de hogares se encuentra inmediatamente antes de Fuentes y calidad en la navegación. El Tipo PASE vacío se muestra como **No es PASE**, por convención solicitada; se conserva tipo_pase_original y el campo PASE original.

- **Usuarios registrados:** Usua_ID distintos del padrón con RENABAP vinculado.
- **Consumidores con registro:** usuarios con una medición de consumo válida en el último bimestre disponible, incluidos los valores menores a 100.
- **Consumo bajo persistente:** menos de 100 durante al menos dos bimestres consecutivos (cuatro meses) que terminan en el último período disponible. Un período ausente o un valor de 100 o más corta la secuencia.
- **Sin consumo:** sin registros válidos en todo el historial disponible, según lo definido por el usuario. La falta de dato solo en el último bimestre se informa aparte y no alcanza este criterio.
- **Posibles colgados / casos a revisar:** unión sin duplicados de persistencia baja y ausencia de historial. Es una señal de los datos, no una constatación de conexión irregular.
- **Sin medidor estimado:** máximo(Viviendas Estimadas − usuarios registrados, 0) para cada barrio. La fuente contiene viviendas estimadas, no familias ni medidores observados. Se supone un usuario por vivienda. La brecha no se calcula restando solo los consumidores con lectura.
- **Mediana barrial:** último bimestre entre mediciones de consumo mayores o iguales a 100. La mediana conjunta se calcula sobre todos los usuarios elegibles seleccionados, no promediando medianas de barrios.

Las incidencias de posibles colgados usan usuarios registrados como denominador; las brechas de medición usan viviendas estimadas. Los barrios con cero usuarios no tienen una incidencia de usuarios calculable, pero sí pueden tener brecha estimada. Los usuarios sin barrio no se asignan por suposición. Se conservan los casos donde el padrón excede las viviendas estimadas para revisión. Se exportan indicadores barriales y los usuarios que cumplen el criterio.

Comparar grupos permite seleccionar hasta 12 categorías, ver su evolución por mediana o media y contrastar sus distribuciones mediante cajas para un período elegido. Se muestra la diferencia absoluta y porcentual de mediana respecto a un grupo de referencia en cada período, con denominadores y cobertura. Los diagramas de caja no dibujan valores extremos individualmente, pero estos sí participan de los cálculos. La comparación es descriptiva y no estima impacto causal.

Paleta aplicada a partir de la referencia del usuario: azul EdERSA, amarillo y fondo claro.

## Extender la aplicación

La lógica general está en `model.py`, la preparación de encuestas en `surveys.py`, el relato visual en `characterization.py`, los vínculos territoriales en `interventions.py`, el gráfico de consumos en `charts.py`, las conexiones en `data_access.py` y la navegación en `app.py`. Para consolidar futuras visitas conviene incorporar un hogar_id estable. El mapa puede consumir esas mismas fuentes, sin depender de Streamlit.

## Verificación

```powershell
python -m pip install pytest
python -m pytest tests -q
```

Las pruebas del modelo usan casos con NIS compartido, consumos duplicados, ceros y faltantes. Las de interfaz recorren pantallas y filtros con la copia local. No prueban las credenciales online del equipo.

### Ficha individual: tendencia y estaciones

Gas figura en Caracterización disponible. La ficha conserva consumo actual, mediana y cantidad de registros. El historial incluye una tendencia lineal general por mínimos cuadrados, calculada con todos los consumos ≥100 del usuario, aunque estén fuera de la ventana visible. Requiere al menos dos períodos válidos y no extrapola más allá del historial apto. Es descriptiva y no ajusta por estacionalidad. Los puntos muestran los valores registrados. Invierno (junio–agosto) usa banda blanca y copo discreto; verano (diciembre–febrero), banda amarilla y sol discreto.

La mediana de la ficha incorpora una mini línea con la tendencia general del historial apto (≥100). Se elimina el KPI y la columna de último consumo; el último valor sigue participando del aviso de consumo crítico cuando supera 1000, igual que la mediana. La tabla indica cuál de los dos activa el aviso. En el historial, una línea en 100 aparece si hay mediciones inferiores y otra en 1000 si hay mediciones críticas; los puntos se distinguen por color.
