import urllib
from cloudsigma.conf import config
import simplejson
import logging
import os
import urlparse
from testing.templates import get_template

__author__ = 'islavov'

LOG = logging.getLogger(__name__)


class ResponseDumper(object):

    def __init__(self, name=None, suffix=None, dump_path=None, req_data_filter=None, resp_data_filter=None):
        self.name = name
        self.suffix = suffix
        self.tmp_name = None
        self.req_data_filter = req_data_filter
        self.resp_data_filter = resp_data_filter

        # If dump path not found/derived,
        if dump_path is None and config.get('dump_path') is not None:
            self.dump_path = os.path.join(os.path.expanduser(config['dump_path']))
        else:
            self.dump_path = dump_path

    def __call__(self, resp, *args, **kwargs):

        if self.dump_path is None:
            return

        if not os.path.exists(self.dump_path):
            LOG.debug("Creating samples path - {}".format(self.dump_path))
            os.makedirs(self.dump_path)

        if not resp.ok:
            LOG.error('Response not OK for dump - {}'.format(resp.text))
            return

        fname = self.get_filename(resp)

        with open(os.path.join(self.dump_path, "request_{}".format(fname, )), "w") as fl:
            LOG.info("Dumping request to {}".format(fl.name))
            if self.req_data_filter:
                data = self.resp_data_filter(resp.request.body)
            else:
                data = resp.request.body
            data = data or ''
            fl.write(self.get_populated_template(
                    "request_template",
                    resp.request,
                    data,
                    path_url=urllib.unquote(resp.request.path_url)))

        with open(os.path.join(self.dump_path, "response_{}".format(fname)), "w") as fl:
            LOG.info("Dumping response to {}".format(fl.name))
            if self.resp_data_filter:
                LOG.info("Filtering response data")
                data = self.resp_data_filter(resp.content)
            else:
                data = resp.content
            fl.write(self.get_populated_template("response_template", resp, data))

        self.tmp_name = None

    def get_filename(self, resp):
        url = urlparse.urlparse(resp.request.path_url)
        path_arr = [segment for segment in url.path.split('/') if segment]

        if self.tmp_name:
            return self.tmp_name
        elif self.name:
            fname = self.name
        else:
            fname = "{}_api_{}_{}".format(resp.request.method, path_arr[1], path_arr[2])
            if len(path_arr) > 3:
                check = path_arr[3]
                if check == 'detail':
                    fname += "_list_detail"
                else:
                    fname += "_detail"
                    if path_arr[4:]:
                        fname += "_" + "_".join(path_arr[4:])

            if url.query:
                query_tuple = urlparse.parse_qsl(url.query)
                for key, val in sorted(query_tuple):
                    if key not in ['limit', 'format']:
                        fname += "_{}_{}".format(key, val)

        if self.suffix:
            fname += "_{}".format(self.suffix)

        return fname

    def get_populated_template(self, template, reqres, data=None, **kwargs):
        if data is not None:
            try:
                data = simplejson.dumps(simplejson.loads(data), sort_keys=True, indent=4)
            except:
                data = ""
        return get_template(template).format(
            reqres=reqres,
            content_type=reqres.headers.get('content-type'),
            data=data,
            **kwargs
    )


class DumpResponse(object):

    def __init__(self, clients=[], *args, **kwargs):
        self.clients = clients
        self.response_dump = ResponseDumper(*args, **kwargs)

    def __call__(self, tmp_name=None):
        if tmp_name is not None:
            self.response_dump.tmp_name = tmp_name
        return self

    def __enter__(self):
        for client in self.clients:
            client.attach_response_hook(self.response_dump)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for client in self.clients:
            client.detach_response_hook()
        self.response_dump.tmp_name = None

    def set_tmp_name(self, val):
        """
        Sets a temporary name for the dump. Dropped after the response is returned.
        """
        self.response_dump.tmp_name = val
