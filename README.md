# 🛡️ Bot de Actividades — Hermandad de World of Warcraft

Bot de Discord en Python (discord.py) para gestionar eventos/actividades de tu hermandad:
inscripciones con botones y formularios (Modals), cierre de inscripciones y registro
de ganadores para eventos grupales.

## Estructura del proyecto

```
wow-bot/
├── main.py                 # Punto de entrada del bot
├── cogs/
│   ├── eventos.py           # Comandos slash (/evento crear, cerrar, etc.)
│   ├── pruebas.py           # Comandos de prueba (/test ganador, bienvenida, equipos_armados)
│   └── vistas.py            # Botones persistentes + Modal de inscripción
├── utils/
│   ├── storage.py           # Persistencia en JSON
├── data/
│   └── eventos.json          # Base de datos (se genera/actualiza sola)
├── requirements.txt
└── .env.example
```

## 1. Requisitos previos

- Python 3.10 o superior
- Una aplicación de Discord con su Bot creado en https://discord.com/developers/applications

## 2. Crear el bot en Discord

1. Entra al [Portal de Desarrolladores de Discord](https://discord.com/developers/applications) y crea una nueva aplicación.
2. Ve a la pestaña **Bot** → **Reset Token** → copia el token (lo necesitarás en el paso 4).
3. En **Bot**, activa el intent **Server Members Intent** si más adelante quieres validar roles del gremio (no es obligatorio para lo que incluye este bot).
4. Ve a **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permisos del bot: `Send Messages`, `Embed Links`, `Read Message History`, `Use Slash Commands`, `Manage Messages` (para editar el mensaje del evento).
5. Copia la URL generada y ábrela en el navegador para invitar el bot a tu servidor.

## 3. Instalación

```bash
cd wow-bot
python -m venv venv
source venv/bin/activate      # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Configuración

Copia `.env.example` a `.env` y rellena tu token:

```bash
cp .env.example .env
```

```
DISCORD_TOKEN=tu_token_aqui
GUILD_ID=tu_id_de_servidor   # opcional, recomendado durante pruebas
ROL_MAESTRO_ID=id_del_rol_legionario_maestro
ROL_OFICIAL_ID=id_del_rol_legionario_oficial
CANAL_AVISOS_ID=id_del_canal_general       # opcional
ROL_AVISOS_ID=id_del_rol_legionarios       # opcional
```

Si configuras `CANAL_AVISOS_ID`, al crear un evento o raid el bot publicará
automáticamente un aviso con el enlace directo a la publicación. Si además
configuras `ROL_AVISOS_ID`, mencionará ese rol (por ejemplo, Legionarios).
El mismo canal y rol reciben siempre un recordatorio 30 minutos antes del inicio.
Además, cada evento o raid puede tener un **recordatorio extra** con la anticipación
que quieras: usa el parámetro `recordatorio_extra` en `crear` o `editar` con valores
como `2h`, `90m`, `1d` o `1d12h` (entre 5 minutos y 30 días; `0` lo quita al editar).
Si al crear o editar ese momento ya pasó, no se envía. Las copias de `/raid duplicar`
y de las raids programadas conservan la anticipación de su raid original.
Las inscripciones que continúen abiertas se cierran automáticamente 3 horas
después de la fecha de cada evento o raid. Las programaciones semanales usan
`ZONA_HORARIA`; cada raid publicada automáticamente puede modificarse después
con `/raid editar`, igual que una raid creada manualmente.

Cada intento de ejecutar un comando slash queda registrado en la salida del bot
con el usuario, sus identificadores de usuario/servidor/canal, el comando completo
y sus parámetros. Los valores extensos se recortan para mantener los logs legibles.

> `GUILD_ID` hace que los comandos slash aparezcan al instante en ese servidor.
> Si lo dejas vacío, la sincronización global puede tardar hasta ~1 hora la primera vez.

## 5. Ejecutar el bot

```bash
python main.py
```

Si todo va bien verás algo como:
```
✅ Conectado como HermandadBot#1234 — 6 comandos sincronizados.
```

## 6. Comandos disponibles

Los permisos se dividen en tres niveles: **Legionario Maestro**, **Legionario
Oficial** y **Público**. Maestro hereda los comandos de Oficial. Los dos roles se
identifican por los IDs configurados en `.env`, por lo que pueden renombrarse en
Discord sin romper los permisos.

| Comando | Descripción |
|---|---|
| `/evento crear titulo tipo_inscripcion fecha hora canal_publicacion [imagen] [canal_inscripciones] [cantidad_equipos] [recordatorio_extra]` | Abre un formulario para la descripción y publica el evento con embed + botones. `cantidad_equipos` es obligatorio solo para Equipos armados |
| `/evento cerrar evento_id` | Cierra inscripciones, deshabilita el botón |
| `/evento editar evento_id [titulo] [descripcion] [fecha] [hora] [imagen] [quitar_imagen] [cantidad_equipos] [recordatorio_extra]` | Edita un evento sin perder participantes o equipos; en Equipos armados permite ampliar o reducir la cantidad de equipos (solo Legionario Maestro) |
| `/evento armar_equipos evento_id` | Abre un panel privado para armar los equipos de un evento de Equipos armados y publicarlos |
| `/evento exportar_inscritos evento_id` | Envía en privado los inscritos de un evento de Equipos armados: un `.txt` con instrucciones listo para pegar en una IA que proponga equipos parejos, y un `.csv` para Excel/Sheets |
| `/evento registrar_ganador evento_id imagen_fondo [ganador] [numero_equipo]` | Publica un banner con fondo personalizado, marca al usuario o equipo ganador y finaliza el evento |
| `/evento listar [estado]` | Lista eventos del servidor (abiertos/cerrados/finalizados) |
| `/evento cancelar evento_id` | Cancela el evento por completo |
| `/test ganador nombre_evento imagen_fondo [ganador] [nombre_equipo]` | Genera una vista previa privada individual o grupal del banner del ganador sin modificar ningún evento |
| `/test equipos_armados [cantidad_equipos] [suplentes] [canal_inscripciones]` | Publica en el canal actual un evento de Equipos armados de prueba con inscritos ficticios (IDs inexistentes, no notifican a nadie) para ensayar `/evento armar_equipos`; se borra con `/evento eliminar` |
| `/test bienvenida` | Genera una vista previa privada de la tarjeta de bienvenida (solo Legionario Maestro) |
| `/raid duplicar raid_id fecha hora` | Duplica una raid conservando sus datos y canales, pero con una fecha y hora nuevas |
| `/raid editar raid_id [titulo] [descripcion] [fecha] [hora] [imagen] [quitar_imagen] [recordatorio_extra]` | Edita una raid sin perder inscritos (solo administradores) |
| `/raid programar raid_id dia_publicacion hora_publicacion` | Usa una raid existente como plantilla y publica una copia nueva cada semana |
| `/raid programaciones` | Lista las programaciones y sus próximas fechas |
| `/raid editar_programacion programacion_id hora_publicacion` | Cambia la hora semanal de publicación |
| `/raid activar_programacion programacion_id activa` | Activa o pausa una programación semanal |
| `/raid eliminar_programacion programacion_id` | Elimina una programación sin borrar las raids ya publicadas |
| `/raid convertir_a_evento raid_id` | Convierte una raid abierta o cerrada en un evento individual, conservando inscritos y mensaje (solo administradores) |
| `/raid eliminar raid_id` | Elimina permanentemente una raid y su mensaje (solo administradores) |
| `/mensaje` | Publica un mensaje de texto normal como el bot en el canal actual; admite saltos de línea y menciones `@Nombre del rol` |
| `/anuncio` | Publica un mensaje embebido como el bot en el canal actual; admite saltos de línea y menciones `@Nombre del rol` |

### Tipos de inscripción

- **Individual**: es solo una lista de asistencia, para eventos que no necesitan equipos.
  Al pulsar **Inscribirse** quedas anotado de inmediato con tu nombre de Discord — no hay
  ningún formulario ni cantidad de equipos.
- **Grupal**: cada inscripción registra un equipo completo ya formado. El formulario
  aparece en dos pasos: primero el nombre del equipo; al enviarlo aparece un botón
  **➡️ Continuar** (Discord no permite abrir un modal directamente desde otro modal),
  que abre el segundo formulario con los 5 roles (Tank, Healer, DPS x3). No existe
  un límite de equipos: se pueden inscribir equipos hasta que se cierren las
  inscripciones. Los equipos quedan fijos desde la inscripción.
- **Equipos armados por la organización**: la inscripción es individual, pero la
  organización arma después equipos parejos de 1 Tank, 1 Healer y 3 DPS. Al crear el
  evento se indica `cantidad_equipos` (máximo 8), que define los cupos: con 3 equipos
  hay 3 Tanks, 3 Healers y 9 DPS (melee y ranged cuentan como DPS). Al pulsar
  **Inscribirse** se elige clase y especialización, y un formulario pide nombre del
  personaje, item level y puntuación de Raider.IO. Si el rol ya está lleno, la persona
  queda como **suplente**; titulares y suplentes se ordenan por orden de inscripción,
  así que si un titular se da de baja o se amplía la cantidad de equipos con
  `/evento editar`, el primer suplente sube solo y se anuncia en `canal_inscripciones`.
  Para apoyarse en una IA, `/evento exportar_inscritos` entrega los inscritos con
  una instrucción ya redactada para que proponga equipos parejos por IO e ilvl.
  Con `/evento armar_equipos` se abre un panel privado donde se elige, equipo por
  equipo, el Tank, el Healer y los 3 DPS entre los inscritos de cada rol (quien ya está
  en un equipo no aparece en los demás), viendo el promedio de ilvl e IO de cada equipo.
  **Publicar equipos** exige que todos estén completos, los muestra en el embed y los
  anuncia en el canal del evento mencionando a cada integrante. Se puede volver a abrir
  el panel para corregirlos y publicarlos otra vez. Los equipos se numeran
  `Equipo #1`, `#2`, … y se usan igual que los grupales en `/evento registrar_ganador`.

### Fecha, hora e imagen

Al crear el evento se piden `fecha` (formato `DD/MM/AAAA`) y `hora` (formato 24h `HH:MM`),
interpretadas con la zona horaria de `ZONA_HORARIA` (variable de entorno, CST/UTC-6 por
defecto). Se muestran en el embed con el formato dinámico de Discord (`📅 Fecha y hora`),
que cada usuario ve automáticamente en su propio huso horario, junto con el tiempo
relativo ("en 3 días" / "hace 3 días"). También se puede adjuntar una `imagen` (banner,
logo del jefe, etc.) que se muestra al final del embed.

### La descripción se pide en un formulario aparte

Los parámetros de un slash command son cajas de texto de una sola línea — Discord no
permite saltos de línea ahí. Por eso, al ejecutar `/evento crear`, después de llenar los
demás campos se abre un formulario (modal) con un campo de texto tipo párrafo para la
**descripción**, que sí admite varias líneas y párrafos como los ves en Discord normalmente.

### Flujo típico

1. Un oficial ejecuta `/evento crear titulo:"Mítico+ semanal" tipo_inscripcion:Individual fecha:30/06/2026 hora:23:00 canal_publicacion:#eventos canal_inscripciones:#inscripciones-log`.
2. Se abre un formulario para escribir la descripción (con saltos de línea) y al enviarlo
   el bot publica el embed con botones en el canal elegido. Cada inscripción/baja se
   anuncia también en `canal_inscripciones` si se configuró, además de actualizar el embed.
3. Cuando ya no se aceptan más inscritos: `/evento cerrar evento_id:1`.
4. Si es grupal, los equipos ya están formados desde la inscripción. Si es de Equipos
   armados, usa `/evento armar_equipos evento_id:1` para formarlos y publicarlos.
5. Al terminar una actividad individual, usa `/evento registrar_ganador evento_id:1 imagen_fondo:banner.png ganador:@usuario`.
   Para una grupal o de Equipos armados, usa `/evento registrar_ganador evento_id:1 imagen_fondo:banner.png numero_equipo:2`.
   El anuncio incluye un banner con el fondo indicado en el comando y, encima, el
   avatar del usuario ganador o el nombre del equipo ganador. El número de equipo es
   el que aparece en el embed (`Equipo #N`); se asigna al inscribirse y no cambia
   aunque otro equipo se dé de baja.

## 7. Persistencia y reinicios

Al reiniciar el bot, `main.py` vuelve a registrar automáticamente los botones de los
eventos que sigan abiertos o cerrados (pero no finalizados), por lo que los botones
**no se rompen** tras un reinicio o caída del bot — siempre que los datos del evento
sigan existiendo (ver siguiente sección).

### Dónde se guardan los datos

- **Sin `DATABASE_URL` configurada** (por ejemplo, corriendo el bot en tu máquina): los
  eventos se guardan en `data/eventos.json`. Cómodo para probar, pero **no sirve para
  producción en Render**: su filesystem no es persistente, así que ese archivo se resetea
  a lo que esté commiteado en git cada vez que se hace un deploy nuevo, perdiendo
  cualquier evento creado después del último commit.
- **Con `DATABASE_URL` configurada**: los eventos se guardan en esa base de datos Postgres
  en vez del archivo JSON, y sobreviven a cualquier deploy. **Es obligatorio configurarla
  en Render** para no perder datos reales de tu hermandad.

Cómo configurarla (gratis):
1. Crea una cuenta en [Supabase](https://supabase.com) o [Neon](https://neon.tech) (ambos
   tienen un plan Postgres gratis permanente) y crea un proyecto/base de datos nueva.
2. Copia el connection string (algo como
   `postgresql://usuario:password@host:5432/basededatos`).
3. En Render: ve a tu servicio → **Environment** → agrega la variable `DATABASE_URL` con
   ese valor, y vuelve a desplegar.
4. En tu máquina, **no** definas `DATABASE_URL` en tu `.env` local (déjala vacía) para
   seguir probando con el archivo JSON — así tu entorno de pruebas nunca toca los datos
   reales de producción.

El bot detecta automáticamente cuál usar: si `DATABASE_URL` existe, usa Postgres
(`utils/storage_pg.py`); si no, usa el archivo JSON (`utils/storage_json.py`). Ambos
implementan las mismas funciones, así que el resto del código no distingue cuál está activo.

## 8. Personalización rápida

- **Cambiar los roles de acceso:** configura `ROL_MAESTRO_ID` y `ROL_OFICIAL_ID`
  en `.env` con los IDs copiados desde Discord. No es necesario modificar código.
- **Modificar la composición de equipos grupales:** ajusta los campos de
  `EquipoRosterModal` en `cogs/vistas.py`.

## 9. Base de datos (ya integrado)

Ver sección 7: `utils/storage.py` elige automáticamente entre Postgres
(`utils/storage_pg.py`, producción) y JSON local (`utils/storage_json.py`, pruebas)
según exista o no `DATABASE_URL`. Los cogs solo dependen de las funciones públicas
(`crear_evento`, `obtener_evento`, `agregar_participante`, etc.), así que si más adelante
quieres cambiar de proveedor de base de datos, solo se toca `utils/storage_pg.py`.
## Formulario de interés PvP

Los oficiales pueden publicar una encuesta persistente para conocer el interés de la comunidad en PvP:

- `/form pvp publicar`: publica el formulario en el mismo canal donde se ejecuta el comando. Cada persona puede inscribir un máximo de dos personajes indicando nombre, clase, especialización y nivel (`Principiante`, `Intermedio` o `Experto`). Volver a inscribir el mismo nombre actualiza ese personaje.
- `/form pvp estadisticas formulario_id:<id>`: muestra todos los totales por rol (Tank, Healer y DPS), clase, especialización y nivel de conocimiento.
- `/form pvp inscritos formulario_id:<id>`: muestra solamente las personas inscritas, con su nombre de Discord y los datos de sus personajes.
- `/form pvp cerrar formulario_id:<id>`: cierra el formulario y desactiva sus botones.

Los comandos requieren el rol `Legionario Oficial`. Los participantes usan **Inscribir personaje** y pueden retirar uno de sus personajes mientras el formulario siga abierto. Las estadísticas muestran el nombre visible de Discord junto a cada personaje inscrito.
## Bienvenida y registro automático

Al entrar una persona, el bot publica una tarjeta con su avatar en el canal de
bienvenida. El registro se inicia desde un panel permanente en otro canal y
asigna `Invitado`, `Legionario` o `Raid` según las respuestas.
Las normas se muestran en páginas efímeras privadas y el botón del formulario
solo aparece después de llegar a la última página.

1. Instala las dependencias con `pip install -r requirements.txt`.
2. Copia tu fondo a `assets/welcome_background.png` (idealmente 900×500 o mayor).
3. Configura en `.env`: `CANAL_BIENVENIDA_ID`, `CANAL_REGISTRO_ID`,
   `ROL_INVITADO_ID`, `ROL_LEGIONARIO_ID`, `ROL_RAID_ID`,
   `WELCOME_BACKGROUND`, `WELCOME_SERVER_NAME` y `NORMAS_REGISTRO_PATH`.
4. En Discord Developer Portal, activa **Server Members Intent**.
5. Dale al bot los permisos **Ver canal**, **Enviar mensajes**, **Adjuntar
   archivos** y **Gestionar roles**. En la jerarquía, coloca el rol del bot por
   encima de Invitado, Legionario y Raid.
6. Edita `assets/normas_registro.txt`, reinicia el bot y ejecuta una vez
   `/publicar_registro` para crear el panel permanente.

## Control de silencio por canal de voz

El comando `/voz panel` publica un botón para el canal de voz elegido. Configura
primero estos valores en `.env` (se pueden separar varios IDs con comas):

```env
VOZ_CANALES_ID=id_canal_raid_1,id_canal_raid_2
VOZ_ROLES_CONTROLADORES_ID=id_rol_raid_leader
VOZ_ROLES_AFECTADOS_ID=id_rol_legionario
VOZ_ROLES_EXENTOS_ID=id_rol_exento_opcional
VOZ_ROL_LIMITE_ID=id_primer_rol_superior_exento
```

Solo los roles controladores pueden publicar o pulsar el botón. Al activarlo,
el bot aplica silencio de servidor a los miembros con un rol afectado, salvo que
tengan un rol exento o el rol límite (o uno superior). Quienes entren después
reciben la misma regla. Al desactivar o abandonar la sala, el bot desmutea solo
a quienes había silenciado el propio control. Antes de activar el silencio, el
bot consulta los roles actuales directamente a Discord, por lo que no es necesario
reiniciarlo después de asignar o retirar un rol.

El bot necesita **Silenciar miembros**, **Ver canal** y **Enviar mensajes**. Su
rol debe estar por encima de todos los roles afectados. El estado activo se
reinicia por seguridad cuando se reinicia el bot.
