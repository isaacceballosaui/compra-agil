#!/usr/bin/env python3
"""Descarga las Compras Ágiles publicadas de construcción en la Región Metropolitana (13)
y O'Higgins (6) desde la API v2 de Mercado Público y genera data/compras.json para la app.
Requiere la variable de entorno MP_TICKET (en GitHub: Settings > Secrets > Actions)."""
import json, os, re, sys, time, unicodedata, urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

BASE = 'https://api2.mercadopublico.cl/v2/compra-agil'
TICKET = os.environ.get('MP_TICKET', '').strip()
REGIONES = {'13': 'RM', '6': 'VI'}
AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, 'data', 'compras.json')
MUESTRA = os.path.join(AQUI, 'data', 'muestra_api.json')

# Palabras clave por rubro (minúsculas, sin tildes). Se evalúan en orden: el primero que calce gana.
RUBROS = {
    'Techumbres': ['techumbre', 'techo', 'cubierta', 'impermeabiliz', 'canaleta', 'hojalateria'],
    'Pintura': ['pintura', 'pintar', 'esmalte', 'latex', 'barniz'],
    'Pisos': ['piso', 'pavimento', 'ceramica', 'porcelanato', 'baldosa', 'vinilico', 'radier'],
    'Gasfitería': ['gasfiter', 'sanitari', 'alcantarillado', 'agua potable', 'lavamanos', 'griferia'],
    'Electricidad': ['electric', 'luminaria', 'tablero', 'cableado', 'iluminacion'],
    'Materiales': ['cemento', 'hormigon', 'arido', 'fierro', 'ladrillo', 'volcanita', 'yeso', 'materiales de construccion', 'ferreteria', 'madera'],
    'Arriendo equipos': ['andamio', 'retroexcavadora', 'betonera', 'arriendo de maquinaria'],
    'Obras menores': ['construccion', 'reparacion', 'remodelacion', 'obras menores', 'obra menor', 'cerco', 'cierre perimetral', 'muro', 'demolicion', 'albanil', 'carpinteria', 'mantencion de infraestructura', 'mejoramiento'],
}
EXCLUIR = ['computador', 'notebook', 'software', 'impresora', 'toner', 'alimento', 'medicamento', 'vehiculo', 'licencia', 'celular']

MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7,
         'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
RE_VISITA = re.compile(r'visita\s+(?:a\s+|en\s+|de\s+)?(?:terreno|obra|tecnica|inspectiva|al\s+lugar)|visita\s+(?:obligatoria|voluntaria)')


def norm(s):
    return unicodedata.normalize('NFD', str(s or '')).encode('ascii', 'ignore').decode().lower()


def llamar(url, intentos=4):
    for i in range(intentos):
        try:
            rq = urllib.request.Request(url, headers={'ticket': TICKET, 'Accept': 'application/json', 'User-Agent': 'compra-agil-app'})
            with urllib.request.urlopen(rq, timeout=45) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404):
                raise
            espera = int(e.headers.get('Retry-After') or 0) or 8 * (i + 1)
            print(f'  HTTP {e.code}, reintento en {espera}s')
            time.sleep(min(espera, 300))
        except Exception as e:
            print(f'  error de red ({type(e).__name__}), reintento')
            time.sleep(8 * (i + 1))
    raise RuntimeError('La API no respondió: ' + url.split('?')[0])


def clave(k):
    return re.sub(r'[^a-z]', '', norm(k))


def buscar(obj, nombres):
    """Primer valor no vacío (búsqueda por niveles) cuyo nombre de campo coincida con alguno de `nombres`."""
    objetivos = {clave(n) for n in nombres}
    cola = [obj]
    while cola:
        o = cola.pop(0)
        if isinstance(o, dict):
            for k, v in o.items():
                if clave(k) in objetivos and v not in (None, '', [], {}):
                    return v
            cola.extend(v for v in o.values() if isinstance(v, (dict, list)))
        elif isinstance(o, list):
            cola.extend(x for x in o if isinstance(x, (dict, list)))
    return None


def texto(v):
    if isinstance(v, dict):
        return texto(buscar(v, ['nombre', 'razon_social', 'descripcion', 'glosa']))
    if isinstance(v, list):
        return ', '.join(texto(x) for x in v if x)
    return '' if v is None else str(v).strip()


def numero(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = re.sub(r'[^\d]', '', str(v).split(',')[0])
    return int(s) if s else None


def fecha(v):
    if not v:
        return None
    s = str(v).strip()
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00')).isoformat()
    except ValueError:
        pass
    for f in ('%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%d/%m/%Y %H:%M', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, f).isoformat()
        except ValueError:
            pass
    return None


def primera_lista(resp):
    cola = [resp]
    while cola:
        o = cola.pop(0)
        if isinstance(o, list) and o and all(isinstance(x, dict) for x in o):
            return o
        if isinstance(o, dict):
            cola.extend(v for v in o.values() if isinstance(v, (dict, list)))
    return []


def rubro_de(t):
    for r, kws in RUBROS.items():
        if any(k in t for k in kws):
            return r
    return None


def detectar_visita(original, anio):
    t = norm(original)
    m = RE_VISITA.search(t)
    if not m:
        return None
    ventana = t[max(0, m.start() - 60): m.end() + 220]
    dia = mes = None
    d = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', ventana)
    if d and 1 <= int(d[1]) <= 31 and 1 <= int(d[2]) <= 12:
        dia, mes = int(d[1]), int(d[2])
        if d[3]:
            anio = int(d[3]) + (2000 if len(d[3]) == 2 else 0)
    else:
        d = re.search(r'(\d{1,2})\s+de\s+(' + '|'.join(MESES) + r')', ventana)
        if d:
            dia, mes = int(d[1]), MESES[d[2]]
    h = re.search(r'(\d{1,2})[:.](\d{2})', ventana)
    iso = None
    if dia:
        try:
            iso = datetime(anio, mes, dia, int(h[1]) if h else 0, int(h[2]) if h else 0).isoformat()
        except ValueError:
            iso = None
    frases = re.split(r'(?<=[.\n])\s*', str(original))
    frase = next((f.strip() for f in frases if 'visita' in norm(f)), '')
    return {'fecha': iso, 'conHora': bool(h), 'texto': frase[:280],
            'obligatoria': 'obligatori' in ventana, 'voluntaria': 'voluntari' in ventana}


def mapear(item, det, reg, rubro):
    def f(*n):
        return (buscar(det, n) if det else None) or buscar(item, n)
    cod = texto(f('codigo', 'codigo_compra', 'id'))
    nombre = texto(f('nombre', 'titulo', 'nombre_compra'))
    desc = texto(f('descripcion', 'descripcion_compra', 'detalle'))
    cierre = fecha(f('fecha_cierre', 'cierre', 'fecha_termino', 'fecha_fin'))
    anio = int(cierre[:4]) if cierre else datetime.now().year
    prods = []
    for p in (f('productos', 'items', 'productos_solicitados', 'detalle_productos') or []):
        if isinstance(p, dict):
            prods.append([texto(buscar(p, ['nombre', 'nombre_producto', 'producto', 'descripcion'])),
                          numero(buscar(p, ['cantidad'])) or 1,
                          texto(buscar(p, ['unidad', 'unidad_medida'])) or 'un'])
    docs = [texto(buscar(d, ['nombre', 'nombre_archivo', 'titulo'])) or 'Adjunto'
            for d in (f('documentos', 'adjuntos', 'archivos') or []) if isinstance(d, dict)]
    plazo = f('plazo_entrega', 'plazo', 'dias_entrega')
    plazo = f'{plazo} días' if isinstance(plazo, (int, float)) else texto(plazo)
    return {
        'id': cod, 'nombre': nombre, 'descripcion': desc, 'region': reg, 'rubro': rubro,
        'organismo': texto(f('organismo', 'nombre_organismo', 'institucion', 'nombre_institucion', 'comprador', 'unidad_compra')),
        'comuna': texto(f('comuna', 'comuna_unidad', 'comuna_entrega', 'comuna_despacho')),
        'direccion': texto(f('direccion_entrega', 'direccion_despacho', 'direccion')),
        'monto': numero(f('presupuesto', 'presupuesto_disponible', 'monto_disponible', 'monto_total', 'monto')),
        'pub': fecha(f('fecha_publicacion', 'publicacion', 'fecha_inicio')),
        'cierre': cierre, 'plazo': plazo, 'productos': prods, 'adjuntos': docs,
        'visita': detectar_visita(nombre + '. ' + desc, anio),
        'url': 'https://buscador.mercadopublico.cl/ficha?code=' + urllib.parse.quote(cod),
    }


def main():
    if not TICKET:
        sys.exit('Falta MP_TICKET. Configúralo como Secret en GitHub (ver LEEME.md).')
    previo = {}
    try:
        with open(SALIDA, encoding='utf-8') as fh:
            data = json.load(fh)
        if not data.get('demo'):
            previo = {c['id']: c for c in data.get('compras', [])}
    except Exception:
        pass

    candidatos, muestra = [], {}
    for cod, reg in REGIONES.items():
        for pag in range(1, 61):
            qs = urllib.parse.urlencode({'region': cod, 'estado': 'publicada', 'tamano_pagina': 50, 'numero_pagina': pag})
            items = primera_lista(llamar(f'{BASE}?{qs}'))
            if items and 'listado' not in muestra:
                muestra['listado'] = items[0]
            for it in items:
                t = norm(texto(buscar(it, ['nombre', 'titulo'])) + ' ' + texto(buscar(it, ['descripcion'])))
                if any(x in t for x in EXCLUIR):
                    continue
                r = rubro_de(t)
                if r:
                    candidatos.append((it, reg, r))
            print(f'Región {cod} · página {pag}: {len(items)} resultados')
            if len(items) < 50:
                break
    print(f'{len(candidatos)} compras de construcción; descargando detalle…')

    def detalle(c):
        it, reg, r = c
        cod = texto(buscar(it, ['codigo', 'codigo_compra', 'id']))
        if cod in previo and previo[cod].get('_det'):
            return previo[cod]
        det = None
        for url in (f'{BASE}/{urllib.parse.quote(cod)}', f'{BASE}?' + urllib.parse.urlencode({'id': cod})):
            try:
                det = llamar(url, 3)
                break
            except Exception:
                continue
        if det and 'detalle' not in muestra:
            muestra['detalle'] = det
        out = mapear(it, det, reg, r)
        out['_det'] = bool(det)
        return out

    with ThreadPoolExecutor(max_workers=3) as ex:
        compras = [c for c in ex.map(detalle, candidatos) if c.get('id')]

    ahora = datetime.now(timezone.utc).isoformat()
    vistos, final = set(), []
    for c in compras:
        if c['id'] in vistos:
            continue
        vistos.add(c['id'])
        if c.get('cierre') and c['cierre'] < ahora[:19]:
            continue
        final.append(c)
    final.sort(key=lambda c: c.get('monto') or 0, reverse=True)

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, 'w', encoding='utf-8') as fh:
        json.dump({'actualizado': ahora, 'demo': False, 'total': len(final), 'compras': final}, fh, ensure_ascii=False, indent=1)
    with open(MUESTRA, 'w', encoding='utf-8') as fh:
        json.dump(muestra, fh, ensure_ascii=False, indent=1)
    print(f'Listo: {len(final)} compras guardadas en data/compras.json')


if __name__ == '__main__':
    main()
