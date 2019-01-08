#!/usr/bin/python
import argparse
import bs4
import json
import logging
import requests
import re
import sys
import ssl
from urllib.request import Request
import urllib.request

TMP_FILE = 'ccmainfo.json'

TITLE = "Titol"
INFO_LINK = "Info"
HQ_VIDEO = "HQ"
MQ_VIDEO = "MQ"
SUBTITLE_1 = "Subs1"
SUBTITLE_2 = "Subs2"

# Ignore SSL certificate errors
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


name_urlbase = "http://www.tv3.cat/pvideo/FLV_bbd_dadesItem_MP4.jsp?idint="
hq_urlbase = "http://www.tv3.cat/pvideo/FLV_bbd_media.jsp?QUALITY=H&PROFILE=IPTV&FORMAT=MP4GES&ID="
subs1_urlbase = "http://dinamics.ccma.cat/pvideo/media.jsp?media=video&version=0s&profile=tv&idint="
subs2_urlbase = "http://www.tv3.cat/p3ac/p3acOpcions.jsp?idint="

SUPER3_URL = "www.ccma.cat/tv3/super3/"
SUPER3_FILTER = "media-object"
TV3_URL = "www.ccma.cat/tv3/alacarta/"
TV3_FILTER = "F-capsaImatge"

hT = False

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
						help='Run without asking for url')
	parser.add_argument('--debug', dest='verbose', action='store_true',
						help='Debug mode')
	parser.set_defaults(verbose=False)
	args = parser.parse_args()
	return args
	
def getTxt(url):
	fhhhh = open(url, "r+", encoding="utf8")
	lsst = fhhhh.readlines()
	urlaltt = ""
	ii = 0
	while (ii < len(lsst)):
		urlaltt += lsst[ii]
		ii = ii + 1;
	return urlaltt

def get_url(args):
	if not args.batch:
		url = input("Write your URL: ")
	else:
		url = args.batch
	if url.find(".html") > -1:
		logger.debug("TV3 link")
		hT = True
		return url, TV3_FILTER
	elif url.find(SUPER3_URL) > -1:
		logger.debug("SUPER3 link")
		return url, SUPER3_FILTER
	elif url.find(TV3_URL) > -1:
		logger.debug("TV3 link")
		return url, TV3_FILTER
	else:
		logger.error("Given URL is not supported.")
		sys.exit(5)


def load_json():
	try:
		json_file = open(TMP_FILE, "r").read()
		j = json.loads(json_file)
		logger.info("Using old temporary list")
	except:
		logger.info("Creating new temporary list")
		j = []
	return j


def create_json(jin):
	j = json.loads(json.dumps(jin))
	logger.info("Rewriting temporary list")
	try:
		with open(TMP_FILE, 'w') as outfile:
			json.dump(j, outfile)
		logger.debug("Done rewriting temporary list")
	except:
		logger.error("Failed to write the temporary list.")
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
	if (url.endswith(".html")):
		html_doc = getTxt(url)	
	else:
		req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
		html_doc = urllib.request.urlopen(req, context=ctx).read()
	soup = bs4.BeautifulSoup(html_doc, 'html.parser')
	logger.info("Parsing URL {}".format(url))
	try:
		capis_meta = soup.find_all('a', class_=parse_filter)
		for capi_meta in capis_meta:
			p = re.compile('/video/([0-9]{7})/$')
			capis.append(p.search(capi_meta['href']).group(1))
	except:
		logger.error("Could not parse given url")
		sys.exit(2)

	capis.reverse()
	first_run = True
	new = False
	for capi in capis:
		logger.debug("Going for ID:{}".format(capi))
		try:
			req = Request(subs1_urlbase + capi, headers={'User-Agent': 'Mozilla/5.0'})
			html_doc = urllib.request.urlopen(req, context=ctx).read()
			soup = bs4.BeautifulSoup(html_doc, 'html.parser')
			j = json.loads(soup.text)
			show = j['informacio']['programa']
		except:
			logger.error("Something went very wrong, can't parse second level url.")
			sys.exit(2)
		txt_file = list()

		if first_run:
			if show not in js:
				logger.debug("Show not in temporary file")
				js.append(show)
				js.append([])
				new = True
			pos = js.index(show) + 1
			first_run = False
		if not new:
			if capi in js[pos]:
				logger.debug("Episode already checked, skipping...")
				continue
		logger.debug("Going for multiple data.")
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
			req = Request(name_urlbase + capi, headers={'User-Agent': 'Mozilla/5.0'})
			html_doc = urllib.request.urlopen(req, context=ctx).read()
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
			i_hq = 0
			if (j['media']['url'][i_hq]['label'] != "720p"): i_hq = 1
			txt_file.append("{}: {}".format(HQ_VIDEO, j['media']['url'][i_hq]['file']))
		except KeyError:
			pass
		# SUBS1
		try:
			txt_file.append("{}: {}".format(SUBTITLE_1, j['subtitols']['url']))
		except KeyError:
			pass
		# SUBS2
		try:
			req = Request(subs2_urlbase + capi, headers={'User-Agent': 'Mozilla/5.0'})
			html_doc = urllib.request.urlopen(req, context=ctx).read()
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
			logger.info("Writing to {}".format(out_name_file))
			outfile.write('\n'.join(txt_file))
			outfile.close()
		except:
			logger.error("Writing episode to file failed.")
			sys.exit(1)
		js[pos].append(capi)
	create_json(js)


if __name__ == '__main__':
	main()
