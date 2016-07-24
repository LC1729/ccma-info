#!/usr/bin/python
import argparse
import bs4
import json
import logging
import requests
import re
import sys

TMP_FILE = 'ccmainfo.json'

TITLE = "Títol"
INFO_LINK = "Info"
HQ_VIDEO = "HQ"
MQ_VIDEO = "MQ"
SUBTITLE_1 = "Subs1"
SUBTITLE_2 = "Subs2"


name_urlbase = "http://www.tv3.cat/pvideo/FLV_bbd_dadesItem_MP4.jsp?idint="
hq_urlbase = "http://www.tv3.cat/pvideo/FLV_bbd_media.jsp?QUALITY=H&PROFILE=IPTV&FORMAT=MP4GES&ID="
subs1_urlbase = "http://dinamics.ccma.cat/pvideo/media.jsp?media=video&version=0s&profile=tv&idint="
subs2_urlbase = "http://www.tv3.cat/p3ac/p3acOpcions.jsp?idint="

SUPER3_URL = "www.ccma.cat/tv3/super3/"
SUPER3_FILTER = "media-object"
TV3_URL = "www.ccma.cat/tv3/alacarta/"
TV3_FILTER = "F-capsaImatge"

###########
# Logging
logger = logging.getLogger('ccmainfo_main')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.WARNING)
# end internal config
############
capis = []


def cli_parse():
    parser = argparse.ArgumentParser(description='CCMA.cat INFO')
    parser.add_argument('--batch', dest='batch', nargs='?', default=False,
                        help="Executar sense demanar l'URL.")
    parser.add_argument('--debug', dest='verbose', action='store_true',
                        help="Activar la depuració.")
    parser.set_defaults(verbose=False)
    args = parser.parse_args()
    return args


def get_url(args):
    if not args.batch:
        url = input("Escrigui la seva adreça URL: ")
    else:
        url = args.batch
    if url.find(SUPER3_URL) > -1:
        logger.debug("Adreça del SUPER3")
        return url, SUPER3_FILTER
    elif url.find(TV3_URL) > -1:
        logger.debug("Adreça de TV3")
        return url, TV3_FILTER
    else:
        logger.error("Aquesta URL no és compatible.")
        sys.exit(5)


def load_json():
    try:
        json_file = open(TMP_FILE, "r").read()
        j = json.loads(json_file)
        logger.info("Utilitzant l'antiga llista temporal.")
    except:
        logger.info("Creant la nova llista temporal.")
        j = []
    return j


def create_json(jin):
    j = json.loads(json.dumps(jin))
    logger.info("Reescrivint la llista temporal.")
    try:
        with open(TMP_FILE, 'w') as outfile:
            json.dump(j, outfile)
        logger.debug("Reescriptura de la llista temporal completada.")
    except:
        logger.error("No s'ha pogut escriure la llista temporal.")
        sys.exit(1)


def remove_invalid_win_chars(value, deletechars):
    for c in deletechars:
        value = value.replace(c, '')
    return value


def main():
    args = cli_parse()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    url, parse_filter = get_url(args)
    js = load_json()

    html_doc = requests.get(url).text
    soup = bs4.BeautifulSoup(html_doc, 'html.parser')
    logger.info("Analitzant l'URL {}".format(url))
    try:
        capis_meta = soup.find_all('a', class_=parse_filter)
        for capi_meta in capis_meta:
            p = re.compile('/video/([0-9]{7})/$')
            capis.append(p.search(capi_meta['href']).group(1))
    except:
        logger.error("No s'ha pogut analitzar l'URL")
        sys.exit(2)

    capis.reverse()
    first_run = True
    new = False
    for capi in capis:
        logger.debug("Aconseguint l'ID:{}".format(capi))
        try:
            html_doc = requests.get(subs1_urlbase + capi).text
            soup = bs4.BeautifulSoup(html_doc, 'html.parser')
            j = json.loads(soup.text)
            show = j['informacio']['programa']
        except:
            logger.error("Alguna cosa ha sortit molt malament, no es pot analitzar el segon nivell d'URL.")
            sys.exit(2)
        txt_file = list()

        if first_run:
            if show not in js:
                logger.debug("No mostrar al fitxer temporal.")
                js.append(show)
                js.append([])
                new = True
            pos = js.index(show) + 1
            first_run = False
        if not new:
            if capi in js[pos]:
                logger.debug("L'episodi ja existeix, saltant-lo...")
                continue
        logger.debug("Aconseguint diverses dades.")
        # HEADER
        try:
            txt_file.append("{} {} ({})".format(show, j['informacio']['capitol'],
                                           j['audiencies']['kantarst']['parametres']['ns_st_ddt']))
        except KeyError:
            try:
                txt_file.append("{} {}".format(show, j['informacio']['capitol']))
            except KeyError:
                txt_file.append(show)
        # INFO
        txt_file.append("{}: {}".format(INFO_LINK, "{}{}".format(name_urlbase, capi)))

        # TITLE
        try:
            html_doc = requests.get(name_urlbase + capi).text
            soup = bs4.BeautifulSoup(html_doc, 'html.parser')
            txt_file.append("{}: {}".format(TITLE, soup.title.text))
        except:
            pass
        # MQ
        try:
            txt_file.append("{}: {}".format(MQ_VIDEO, soup.file.text))
        except:
            pass
        # HQ
        try:
            txt_file.append("{}: {}".format(HQ_VIDEO, j['media']['url']))
        except KeyError:
            pass
        # SUBS1
        try:
            txt_file.append("{}: {}".format(SUBTITLE_1, j['subtitols']['url']))
        except KeyError:
            pass
        # SUBS2
        try:
            html_doc = requests.get(subs2_urlbase + capi).text
            soup = bs4.BeautifulSoup(html_doc, 'html.parser')
            txt_file.append("{}: {}".format(SUBTITLE_2, soup.sub['url']))
        except:
            pass
        txt_file.append("")
        txt_file.append("")
        txt_file.append("")
        try:
            out_name_file = remove_invalid_win_chars(show, '\/:*?"<>|')
            outfile = open('%s.txt' % out_name_file, 'a')
            logger.info("Escrivint a {}".format(out_name_file))
            outfile.write('\n'.join(txt_file))
            outfile.close()
        except:
            logger.error("Error al escriure l'episodi.")
            sys.exit(1)
        js[pos].append(capi)
    create_json(js)


if __name__ == '__main__':
    main()
