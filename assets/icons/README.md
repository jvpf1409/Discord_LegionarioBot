# Íconos personalizados

Pon las imágenes en las subcarpetas `posicion/`, `clase/` y
`especializacion/` (`.png`, `.jpg` o `.gif`). El bot las busca recursivamente y las sube
automáticamente como "application emojis" (le pertenecen al bot, no a un
servidor de Discord puntual) la primera vez que arranca después de agregarlas,
y de ahí en adelante las reutiliza sin volver a subirlas.

El **nombre del archivo** (sin extensión) es el nombre del ícono en el código.
Para los roles de raid, usa exactamente estos nombres:

- `tank.png`
- `healer.png`
- `melee.png`
- `ranged.png`

Reglas del nombre (las exige Discord): solo letras, números y guion bajo,
entre 2 y 32 caracteres, sin espacios ni tildes.

Si no agregas un archivo para alguno de estos roles, el bot sigue funcionando
normal y usa el emoji de reserva (🛡️ ➕ ⚔️ 🏹) definido en `utils/wow_data.py`.

## Íconos de especialización (opcional)

También puedes agregar un ícono por cada combinación de clase + especialización
(aparece en el listado de inscritos y en el select "Selecciona tu especialización").
El nombre debe ser exactamente `{clase}_{especialización}.png`, todo en minúsculas,
sin tildes y con `_` en vez de espacios. Lista completa esperada:

```
guerrero_armas.png                  paladin_sagrado.png
guerrero_furia.png                  paladin_proteccion.png
guerrero_proteccion.png              paladin_reprension.png
cazador_bestias.png                  sacerdote_disciplina.png
cazador_punteria.png                 sacerdote_sagrado.png
cazador_supervivencia.png            sacerdote_sombras.png
picaro_asesinato.png                 caballero_de_la_muerte_sangre.png
picaro_fuera_de_la_ley.png           caballero_de_la_muerte_escarcha.png
picaro_sutileza.png                  caballero_de_la_muerte_profano.png
chaman_elemental.png                 mago_arcano.png
chaman_mejora.png                    mago_fuego.png
chaman_restauracion.png              mago_escarcha.png
brujo_afliccion.png                  monje_maestro_cervecero.png
brujo_demonologia.png                monje_viajero_del_viento.png
brujo_destruccion.png                monje_tejedor_de_niebla.png
druida_equilibrio.png                cazador_de_demonios_asolamiento.png
druida_feral.png                     cazador_de_demonios_venganza.png
druida_guardian.png                  evocador_devastacion.png
druida_restauracion.png              evocador_preservacion.png
                                      evocador_aumento.png
```

Si te queda alguna duda de un nombre exacto, corre esto desde la raíz del proyecto:

```
python -c "from utils.wow_data import CLASES, nombre_icono_especializacion
for clase, specs in CLASES.items():
    for especializacion, rol in specs:
        print(f'{nombre_icono_especializacion(clase, especializacion)}.png')"
```

Al igual que con los roles: si no agregas un ícono para alguna especialización,
simplemente no se muestra ninguno ahí — el bot no se rompe por esto.

Después de agregar o cambiar un archivo, reinicia el bot para que lo detecte
y lo suba (o usa `scripts/refrescar_iconos.py <nombre>` si ya existía uno con
ese nombre y solo cambiaste la imagen).
