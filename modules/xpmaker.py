import os
import shutil
import tempfile
from datetime import datetime

from modules import article
from modules import xml_utils
from modules import java_xml_utils
from modules import xpchecker


DEFAULT_VERSION = '1.0'
PMC_PATH = './../../pmc'
XSL_SGML2XML = {}
XSL_SGML2XML['3.0'] = PMC_PATH + '/v3.0/xsl/sgml2xml/sgml2xml.xsl'
XSL_SGML2XML['1.0'] = PMC_PATH + '/j1.0/xsl/sgml2xml/sgml2xml.xsl'

DTD_FILENAME = {}
DTD_FILENAME['3.0'] = PMC_PATH + '/v3.0/dtd/journalpublishing3.dtd'
DTD_FILENAME['1.0'] = PMC_PATH + '/j1.0/dtd/jats1.0/JATS-journalpublishing1.dtd'

DOCTYPE = {}
DOCTYPE['3.0'] = '<!DOCTYPE article PUBLIC "-//NLM//DTD Journal Publishing DTD v3.0 20080202//EN" "{DTD_FILENAME}">'
DOCTYPE['1.0'] = '<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.0 20120330//EN" "{DTD_FILENAME}">'

XSL_REPORT = {}
XSL_REPORT['3.0'] = PMC_PATH + '/v3.0/xsl/nlm-style-4.6.6/style-reporter.xsl'
XSL_REPORT['1.0'] = PMC_PATH + '/j1.0/xsl/nlm-style-5.4/style-reporter.xsl'

XSL_REPORT_PREP = {}
XSL_REPORT_PREP['3.0'] = PMC_PATH + '/v3.0/xsl/scielo-style/stylechecker.xsl'
XSL_REPORT_PREP['1.0'] = PMC_PATH + '/j1.0/xsl/scielo-style/stylechecker.xsl'


def doctype(version):
    return DTD_FILENAME.get(version, DOCTYPE[DEFAULT_VERSION])


def dtd_filename(version):
    return DTD_FILENAME.get(version, DTD_FILENAME[DEFAULT_VERSION])


def xsl_sgml2xml(version):
    return XSL_SGML2XML.get(version, XSL_SGML2XML[DEFAULT_VERSION])


def xsl_prep_report(version):
    return XSL_REPORT_PREP.get(version, XSL_REPORT_PREP)


def xsl_report(version):
    return XSL_REPORT.get(version, XSL_REPORT)


class XMLContent(object):

    def __init__(self, content):
        self.content = content

    def fix_dtd_location(self, dtd_filename, doctype):
        if not dtd_filename in self.content:
            if not '<?xml ' in self.content:
                self.content = '<?xml version="1.0" encoding="utf-8"?>\n' + self.content

            if '<!DOCTYPE' in self.content:
                old_doctype = self.content[self.content.find('<!DOCTYPE'):]
                old_doctype = old_doctype[0:old_doctype.find('>')+1]
                self.content = self.content.replace(old_doctype, '')
            if not '<!DOCTYPE' in self.content:
                self.content = self.content.replace('\n<article ', doctype.replace('{DTD_FILENAME}', dtd_filename) + '\n<article ')

    def fix(self):
        self.content = self.content[0:self.content.rfind('>')+1]
        self.content = self.content[self.content.find('<'):]
        self.content = self.content.replace(' '*2, ' '*1)
        if xml_utils.is_xml_well_formed(self.content) is None:
            self._fix_style_tags()
        if xml_utils.is_xml_well_formed(self.content) is None:
            self._fix_open_close()

    def _fix_open_close(self):
        changes = []
        parts = self.content.split('>')
        for s in parts:
            if '<' in s:
                if not '</' in s and not '<!--' in s and not '<?' in s:

                    s = s[s.find('<')+1:]
                    if ' ' in s and not '=' in s:
                        test = s[s.find('<')+1:]
                        changes.append(test)
        for change in changes:
            print(change)
            self.content = self.content.replace('<' + test + '>', '[' + test + ']')

    def _fix_style_tags(self):
        rcontent = self.content
        tags = ['italic', 'bold', 'sub', 'sup']
        tag_list = []
        for tag in tags:
            rcontent = rcontent.replace('<' + tag.upper() + '>', '<' + tag + '>')
            rcontent = rcontent.replace('</' + tag.upper() + '>', '</' + tag + '>')
            tag_list.append('<' + tag + '>')
            tag_list.append('</' + tag + '>')
            rcontent = rcontent.replace('<' + tag + '>',  'BREAKBEGINCONSERTA<' + tag + '>BREAKBEGINCONSERTA').replace('</' + tag + '>', 'BREAKBEGINCONSERTA</' + tag + '>BREAKBEGINCONSERTA')
        if self.content != rcontent:
            parts = rcontent.split('BREAKBEGINCONSERTA')
            self.content = self._fix_problem(tag_list, parts)
        for tag in tags:
            self.content = self.content.replace('</' + tag + '><' + tag + '>', '')

    def _fix_problem(self, tag_list, parts):
        expected_close_tags = []
        ign_list = []
        debug = False
        k = 0
        for part in parts:
            if part in tag_list:
                tag = part
                if debug:
                    print('\ncurrent:' + tag)
                if tag.startswith('</'):
                    if debug:
                        print('expected')
                        print(expected_close_tags)
                        print('ign_list')
                        print(ign_list)
                    if tag in ign_list:
                        if debug:
                            print('remove from ignore')
                        ign_list.remove(tag)
                        parts[k] = ''
                    else:
                        matched = False
                        if len(expected_close_tags) > 0:
                            matched = (expected_close_tags[-1] == tag)
                            if not matched:
                                if debug:
                                    print('not matched')
                                while not matched and len(expected_close_tags) > 0:
                                    ign_list.append(expected_close_tags[-1])
                                    parts[k-1] += expected_close_tags[-1]
                                    del expected_close_tags[-1]
                                    matched = (expected_close_tags[-1] == tag)
                                if debug:
                                    print('...expected')
                                    print(expected_close_tags)
                                    print('...ign_list')
                                    print(ign_list)

                            if matched:
                                del expected_close_tags[-1]
                else:
                    expected_close_tags.append(tag.replace('<', '</'))
            k += 1
        return ''.join(parts)


def rename_embedded_img_href(content, xml_name, new_href_list):
    content = content.replace('<graphic href="?', '--FIXHREF--<graphic href="?')
    items = content.split('--FIXHREF--')
    new = ''
    i = 0
    for item in items:
        if item.startswith('<graphic href="?'):
            s = item[item.find('?'):]
            new += '<graphic href="' + xml_name + new_href_list[i] + s[s.find('"'):]
            i += 1
        else:
            new += item
    return new


def html_img_src(html_content):
    #[graphic href=&quot;?a20_115&quot;]</span><img border=0 width=508 height=314
    #src="a20_115.temp_arquivos/image001.jpg"><span style='color:#33CCCC'>[/graphic]
    html_content = html_content.replace('[graphic href="?', '[graphic href="?' + '"--FIXHREF--FIXHREF')
    items = [item for item in html_content.split('--FIXHREF--') if item.startswith('FIXHREF')]
    img_src = []
    for item in items:
        if ' src="' in item:
            item = item[item.find(' src="') + len(' src="')]
            item = item[0:item.find('"')]
            item = item[item.find('/') + 1:]
            if len(item) > 0:
                img_src.append(item)
    return img_src


def extract_embedded_images(xml_name, content, html_filename, dest_path):
    if content.find('href="?' + xml_name):
        html_content = open(html_filename, 'r').read()
        embedded_img_files = html_img_src(html_content)
        embedded_img_path = os.path.dirname(html_filename)
        content = rename_embedded_img_href(content, xml_name, embedded_img_files)
        for item in embedded_img_files:
            if os.path.isfile(embedded_img_path + '/' + item):
                shutil.copyfile(embedded_img_path + '/' + item, dest_path + '/' + xml_name + item)
    return content


def normalize_sgmlxml(xml_name, content, src_path, version, html_filename):
    content = extract_embedded_images(xml_name, content, html_filename, src_path)
    if not xml_utils.is_xml_well_formed(content):
        content = fix_xml(content)
    if xml_utils.is_xml_well_formed(content) is not None:
        content = java_xml_utils.xml_content_transform(content, xsl_sgml2xml(version))
    return content


def fix_xml(content):
    xml_fix = XMLContent(content)
    xml_fix.fix()
    if not xml_fix.content == content:
        content = xml_fix.content
    return content


def hdimages_to_jpeg(source_path, jpg_path, replace=False):
    try:
        import Image
        IMG_CONVERTER = True
    except:
        IMG_CONVERTER = False

    if IMG_CONVERTER:
        for item in os.listdir(source_path):
            image_filename = source_path + '/' + item
            jpg_filename = source_path + '/' + item[0:item.rfind('.')] + '.jpg'
            if item.endswith('.tiff') or item.endswith('.eps') or item.endswith('.tif'):
                doit = False
                if os.path.isfile(jpg_filename):
                    if replace:
                        doit = True
                else:
                    doit = True
                if doit:
                    try:
                        im = Image.open(image_filename)
                        im.thumbnail(im.size)
                        im.save(jpg_filename, "JPEG")
                    except Exception as inst:
                        print('Unable to generate ' + jpg_filename)
                        print(inst)


def clean_folder(path):
    if os.path.isdir(path):
        for f in os.listdir(path):
            if os.path.isfile(path + '/' + f):
                os.unlink(path + '/' + f)
    else:
        os.makedirs(path)


def delete_files(files):
    for f in files:
        if os.path.isfile(f):
            os.unlink(f)


def xml_paths(src):
    now = datetime.now().isoformat().replace(':', '').replace('T', '').replace('-', '')
    now = now[0:now.find('.')]

    if os.path.isfile(src):
        path = os.path.dirname(src) + '_' + now
    else:
        path = src + '_' + now

    scielo_pkg_path = path + '/scielo_package'
    pmc_pkg_path = path + '/pmc_package'
    report_path = path + '/errors'
    wrk_path = path + '/wrk'
    preview_path = None
    return (scielo_pkg_path, pmc_pkg_path, report_path, preview_path, wrk_path)


def markup_paths(source_path, sgmxml_filename):
    sgmxml_path = os.path.dirname(sgmxml_filename)
    markup_xml_path = os.path.dirname(source_path)

    scielo_pkg_path = markup_xml_path + '/scielo_package'
    pmc_pkg_path = markup_xml_path + '/pmc_package'
    report_path = markup_xml_path + '/errors'
    preview_path = None
    wrk_path = sgmxml_path
    return (scielo_pkg_path, pmc_pkg_path, report_path, preview_path, wrk_path)


def markup_src_path(sgmxml_filename):
    # sgmxml_path = serial/acron/issue/pmc/pmc_work/article
    # sgmxml_path = serial/acron/issue/markup_xml/work/article
    xml_name = os.path.basename(sgmxml_filename)
    sgmxml_path = os.path.dirname(sgmxml_filename)

    # markup_xml_path = serial/acron/issue/pmc
    # markup_xml_path = serial/acron/issue/markup_xml
    markup_xml_path = os.path.dirname(os.path.dirname(sgmxml_path))

    # other files path = serial/acron/issue/pmc/src or serial/acron/issue/pmc/pmc_src
    # other files path = serial/acron/issue/markup_xml/src
    source_path = markup_xml_path + '/src'
    if not os.path.isdir(source_path):
        source_path = markup_xml_path + '/pmc_src'
    if not os.path.isdir(source_path):
        os.makedirs(source_path)
    shutil.copyfile(sgmxml_filename, source_path + '/' + xml_name)
    return source_path


def files_and_paths(xml_source):
    if xml_source.endswith('.sgm.xml'):
        f = xml_source
        ctrl_filename = f.replace('.sgm.xml', '.ctrl.txt')
        source_path = markup_src_path(f)
        xml_files = [source_path + '/' + os.path.basename(f)]
        scielo_pkg_path, pmc_pkg_path, report_path, preview_path, wrk_path = markup_paths(source_path, f)
        #version = 'j1.0'
    else:
        if os.path.isfile(xml_source):
            xml_files = [xml_source]
        else:
            xml_files = [xml_source + '/' + f for f in os.listdir(xml_source) if f.endswith('.xml')]
        ctrl_filename = None
        scielo_pkg_path, pmc_pkg_path, report_path, preview_path, wrk_path = xml_paths(xml_source)

    return (ctrl_filename, xml_files, scielo_pkg_path, pmc_pkg_path, report_path, preview_path, wrk_path)


def format_new_name(doc, param_acron='', original_xml_name=''):
    def format_last_part(fpage, seq, elocation_id, order, doi, issn):
        def normalize_len(fpage):
            fpage = '00000' + fpage
            return fpage[-5:]
        print((fpage, seq, elocation_id, order, doi, issn))
        r = None
        if r is None:
            if fpage is not None:
                r = normalize_len(fpage)
                if seq is not None:
                    r += '-' + seq
        if r is None:
            if elocation_id is not None:
                r = elocation_id
        if r is None:
            if doi is not None:
                doi = doi[doi.find('/')+1:]
                if issn in doi:
                    doi = doi[doi.find(issn) + len(issn):]
                doi = doi.replace('.', '_').replace('-', '_')
                r = doi
        if r is None:
            if order is not None:
                r = normalize_len(order)
        return r
    r = ''
    vol, issueno, fpage, seq, elocation_id, order, doi = doc.volume, doc.number, doc.fpage, doc.fpage_seq, doc.elocation_id, doc.order, doc.doi
    issn = doc.e_issn if doc.e_issn else doc.print_issn
    suppl = doc.volume_suppl if doc.volume_suppl else doc.number_suppl
    if original_xml_name != '':
        issn = original_xml_name[0:9]
    last = format_last_part(fpage, seq, elocation_id, order, doi, issn)
    if issueno:
        if issueno == 'ahead' or issueno == '00':
            issueno = None
        else:
            if len(issueno) <= 2:
                issueno = '00' + issueno
                issueno = issueno[-2:]
    if suppl:
        suppl = 's' + suppl if suppl != '0' else 'suppl'
    parts = [issn, param_acron, vol, issueno, suppl, last]
    r = '-'.join([part for part in parts if part is not None and not part == ''])
    return r


def href_attach_type(parent_tag, tag):
    if 'suppl' in tag or 'media' == tag:
        attach_type = 's'
    elif 'inline' in tag:
        attach_type = 'i'
    elif parent_tag in ['equation', 'disp-formula']:
        attach_type = 'e'
    else:
        attach_type = 'g'
    return attach_type


def get_curr_and_new_href_list(xml_name, new_name, href_list):
    r = []
    attach_type = ''
    for href, attach_type, attach_id in href_list:
        if attach_id is None:
            attach_name = href.replace(xml_name, '')
        else:
            attach_name = attach_id + href[href.rfind('.'):]
        new = new_name + '-' + attach_type + attach_name
        r.append((href, new))
    return list(set(r))


def get_attach_info(doc):
    items = []
    for href_info in doc.hrefs:
        attach_type = href_attach_type(href_info.parent.tag, href_info.element_name)
        attach_id = href_info.id
        items.append((href_info.src, attach_type, attach_id))
    return items


def replace_hrefs(content, curr_and_new_href_list):
    #print(curr_and_new_href_list)
    for current, new in curr_and_new_href_list:
        print(current + ' => ' + new)
        content = content.replace('href="' + current, 'href="' + new)
    return content


def normalize_hrefs(content, acron, xml_name):
    curr_and_new_href_list = []
    if xml_utils.is_xml_well_formed(content) is not None:
        doc = article.Article(content)
        new_name = format_new_name(doc, acron, xml_name)
        attach_info = get_attach_info(doc)
        print('href_list')
        print(attach_info)
        curr_and_new_href_list = get_curr_and_new_href_list(xml_name, new_name, attach_info)
        print(curr_and_new_href_list)
        content = replace_hrefs(content, curr_and_new_href_list)
    return (new_name, curr_and_new_href_list, content)


def pack_related_files(src_path, xml_name, new_name, dest_path, curr_and_new_href_list):
    not_found = []
    related_files_list = []
    href_files_list = []
    href_list = []
    for f in os.listdir(src_path):
        if f.startswith(xml_name + '.') and not f.endswith(xml_name + '.sgm.xml'):
            new = f.replace(xml_name, new_name)
            related_files_list.append((f, new))
            shutil.copyfile(src_path + '/' + f, dest_path + '/' + new)
    for curr, new in curr_and_new_href_list:
        href_list.append((curr, new))
        f = src_path + '/' + curr
        if os.path.isfile(f):
            if curr.rfind('.') > 0:
                curr_name = curr[0:curr.rfind('.')]
                new_name = new[0:new.rfind('.')]
            else:
                curr_name = curr
                new_name = new
            for f in [f for f in os.listdir(src_path) if f.startswith(curr_name + '.')]:
                ext = f[f.rfind('.'):] if f.rfind('.') > 0 else ''
                href_files_list.append((f, new_name + ext))
                shutil.copy(src_path + '/' + f, dest_path + '/' + new_name + ext)
        else:
            not_found.append(curr)
    return (not_found, related_files_list, href_files_list, href_list)


def files_report(xml_name, new_name, src_path, dest_path, related_files_list, href_files_list, href_list, not_found):
    def display_sorted(pair):
        r = sorted(['   ' + c + ' => ' + n for c, n in pair])
        return '\n'.join(r)

    log = []

    log.append('Source path:   ' + src_path)
    log.append('Package path:  ' + dest_path)
    log.append('Source XML name:   ' + xml_name)
    log.append('Generated XML name:' + new_name)

    log.append('\nTotal of related files: ' + str(len(related_files_list)))
    log.append(display_sorted(related_files_list))

    log.append('\nTotal of @href in XML: ' + str(len(href_list)))
    log.append(display_sorted(href_list))

    log.append('\nPacking @href files: ' + str(len(href_files_list)))
    log.append(display_sorted(href_files_list))

    if len(not_found) > 0:
        log.append('\nERROR: Total of @href files not found in ' + src_path + ':')
        log.append(display_sorted(not_found))
    return '\n'.join(log)


def generate_article_xml_package(xml_filename, scielo_pkg_path, report_path, wrk_path, version, acron):
    xml_path = os.path.dirname(xml_filename)
    xml_file = os.path.basename(xml_filename)

    xml_name = xml_file.replace('.sgm.xml', '').replace('.xml', '')
    xml_wrk_path = wrk_path + '/' + xml_name

    err_filename = report_path + '/' + xml_name + '.err.txt'

    clean_folder(xml_wrk_path)
    delete_files([err_filename])

    is_sgmxml = xml_filename.endswith('.sgm.xml')
    html_filename = ''

    content = open(xml_filename, 'r').read()

    content = xml_utils.convert_entities_to_chars(content)
    if is_sgmxml:
        html_filename = xml_wrk_path + '/' + xml_name + '.temp.htm'
        if not os.path.isfile(html_filename):
            html_filename += 'l'
        content = normalize_sgmlxml(xml_name, content, xml_path, version, html_filename)

    if xml_utils.is_xml_well_formed(content) is None:
        new_xml_filename = scielo_pkg_path + '/incorrect_' + xml_name + '.xml'
        report_content = xml_file + ' is not well formed\nOpen ' + new_xml_filename + ' using an XML Editor.'
        r = False
    else:
        new_name = xml_name
        doc = article.Article(content)
        attach_info = get_attach_info(doc)

        print('attach_info')
        print(attach_info)

        if is_sgmxml:
            new_name = format_new_name(doc, acron, xml_name)
            curr_and_new_href_list = get_curr_and_new_href_list(xml_name, new_name, attach_info)
            content = normalize_hrefs(content, curr_and_new_href_list)
        else:
            curr_and_new_href_list = [(href, href) for href, attach_type, attach_id in attach_info]
        print(curr_and_new_href_list)

        # pack files
        not_found, related_files_list, href_files_list, href_list = pack_related_files(xml_path, xml_name, new_name, scielo_pkg_path, curr_and_new_href_list)
        r = True
        new_xml_filename = scielo_pkg_path + '/' + new_name + '.xml'
        report_content = files_report(xml_name, new_name, xml_path, scielo_pkg_path, related_files_list, href_files_list, href_list, not_found)
    try:
        open(new_xml_filename, 'w').write(content)
    except:
        print('ERROR: Unable to create ' + new_xml_filename)
    try:
        open(err_filename, 'w').write(report_content)
    except:
        print('ERROR: Unable to create ' + err_filename)

    return (r, new_xml_filename, err_filename)


def generate_issue_xml_package(xml_files, scielo_pkg_path, report_path, wrk_path, acron, version='1.0'):
    reports = {}
    hdimages_to_jpeg(scielo_pkg_path, scielo_pkg_path, False)
    for xml_filename in xml_files:
        r, new_xml_filename, err_filename = generate_article_xml_package(xml_filename, scielo_pkg_path, report_path, wrk_path, version, acron)
        reports[xml_filename] = (r, new_xml_filename, err_filename)
    return reports


def apply_dtd(content, dtd_filename, doctype):
    xml_str = XMLContent(content)
    xml_str.fix_dtd_location(dtd_filename, doctype)
    return xml_str.content


def apply_check_list(xml_filename, dtd_validation_report_filename, style_checker_report_filename):
    def get_temp_filename(xml_filename):
        temp_dir = tempfile.mkdtemp()
        return temp_dir + '/' + os.path.basename(xml_filename)

    #well_formed, is_dtd_valid, report_ok, preview_ok, output_ok = (False, False, False, False, False)
    xml = xml_utils.is_xml_well_formed(xml_filename)
    if xml:
        version = xml.find('.').attrib.get('dtd-version', DEFAULT_VERSION)

        content = open(xml_filename, 'r').read()
        content = apply_dtd(dtd_filename(version), doctype(version))

        temp_filename = get_temp_filename(xml_filename)
        open(temp_filename, 'w').write(content)

        is_valid_dtd = xpchecker.dtd_validation(temp_filename, dtd_validation_report_filename)
        is_valid_style = xpchecker.style_validation(temp_filename, style_checker_report_filename, xsl_prep_report(version), xsl_report(version))

        os.unlink(temp_filename)
        shutil.rmtree(os.path.dirname(temp_filename))

    return (xml, is_valid_dtd, is_valid_style)


def evaluate_article_xml_package(xml_name, new_name, scielo_pkg_path, report_path):
    xml_filename = scielo_pkg_path + '/' + new_name + '.xml'
    report_content = ''
    dtd_validation_report_filename = report_path + '/' + xml_name + '.dtd.txt'
    style_checker_report_filename = report_path + '/' + xml_name + '.rep.html'
    delete_files([dtd_validation_report_filename, style_checker_report_filename])

    if os.path.isfile(xml_filename):
        xml, is_valid_dtd, is_valid_style = apply_check_list(xml_filename, dtd_validation_report_filename, style_checker_report_filename)
        if xml is None:
            report_content = 'XML is not well formed: ' + xml_filename + '\nProblem to load XML file. See ' + scielo_pkg_path + '/incorrect_' + xml_name + '.xml'
            open(dtd_validation_report_filename, 'w').write(report_content)


def responde_to_markup(ctrl_filename, dtd_validation_report_filename):
    if ctrl_filename:
        import time
        stop_after = 60 * 5
        start = time.time()
        doit = True
        while doit and not os.path.isfile(dtd_validation_report_filename):
            doit = ((time.time() - start) < stop_after)
        if os.path.isfile(dtd_validation_report_filename):
            open(ctrl_filename, 'w').write('done')
        else:
            open(ctrl_filename, 'w').write('interrupted')