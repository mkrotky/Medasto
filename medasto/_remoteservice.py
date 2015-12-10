"""Internal module for connecting to the Medasto Server.

The class 'RemoteService' is instantiated within the ClientService. All
relevant settings are given to the 'ClientService' constructor and then
propagated to this class.

The only field that one might want to adjust here directly is LOG_LEVEL.
"""
import http.client
import logging
import ssl
import base64
import json
import shutil
import os
import time

__author__ = 'Michael Krotky'

LOG_LEVEL = logging.WARN


class RemoteService:

    _REDIRECT_URL = "redirect.medasto.com"
    _API_CONTEXT = "api"

    logger = logging.getLogger(__name__)

    def __init__(self, customerid, username, password, wait_after_error=10, max_tries_on_error=10):
        """
        Does not tolerate errors --> fails on the first encountered error.

        A connection to the Medasto Server must be available when creating an instance of this class.
        """

        # log configuration..
        self.logger.setLevel(LOG_LEVEL)
        consoleout = logging.StreamHandler()
        consoleout.setLevel(LOG_LEVEL)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        consoleout.setFormatter(formatter)
        self.logger.addHandler(consoleout)

        self.customerid = customerid
        self.wait_after_error = wait_after_error
        self.max_tries_on_error = max_tries_on_error
        self.iscancel = False

        self._sessionid = None
        self._userid = -1
        self.current_projectid = -1

        userandpassb64 = base64.b64encode((username + ":" + password).encode('UTF-8'))
        self._credentialsb64 = userandpassb64.decode(encoding='UTF-8')

        try:
            conn = http.client.HTTPConnection(self._REDIRECT_URL)
            conn.request("GET", "/" + customerid + ".txt")
            res = conn.getresponse()
            content = res.read()
            contentstr = content.decode(encoding='UTF-8')
            self.serverurl = contentstr[:contentstr.index("/")]
        except http.client.HTTPException as ex:
            print(ex)
            raise
        else:
            try:
                self._login()
            except BadCredentialsMedEx:
                raise  # calling code must know this asap
            except (UserSessionsExceededMedEx, ConnectionMedEx, MedastoException):
                self.logger.logwarn("Recoverable error when instantiating class %s. Execution will continue.",
                                    RemoteService.__name__, exc_info=True)
        finally:
            if conn is not None:
                conn.close()

    def _login(self):
        try:
            authvalue = "AuthRequest " + self._credentialsb64
            headers = {"Authorization": authvalue}
            conns = self._connection()
            conns.request("GET", self._relbaseurl(), headers=headers)
            res = conns.getresponse()
            if res.status == 260:
                self._sessionid = res.getheader("SessionId")
                self._userid = res.getheader("UserId")
            elif res.status == 462:
                raise BadCredentialsMedEx
            elif res.status == 464:
                raise UserSessionsExceededMedEx
            else:
                raise MedastoException("Unexpected StatusCode in response when trying to login: " + res.status)

        except http.client.HTTPException as ex:
            raise ConnectionMedEx from ex
        except (UserSessionsExceededMedEx, BadCredentialsMedEx, MedastoException):
            raise
        finally:
            if conns is not None:
                conns.close()

    def _reniewsession(self):
        try:
            self._login()

            if self.current_projectid != -1:
                self._dorequest("project-select/" + str(self.current_projectid))

        except (BadCredentialsMedEx, InsuffAuthMedEx, ServerProcessingMedEx, PleaseAuthenticateMedEx):
            raise
        except UserSessionsExceededMedEx:
            self.logger.warn("Error while creating a new session.", exc_info=True)
            time.sleep(self.wait_after_error)
        except (ConnectionMedEx, MedastoException):
            self.logger.warn("Error while creating a new session.", exc_info=True)

    def request(self, url, method='GET', body=None, contenttype='application/json', accept='application/json',
                extra_headers=None, decode_response=True):

        tries = 0
        last_ex = None
        while (tries < self.max_tries_on_error) and (not self.iscancel):
            try:
                result = self._dorequest(url, method, body, contenttype, accept, extra_headers, decode_response)
                return result

            except PleaseAuthenticateMedEx as ex:
                #  login + select project + try again
                last_ex = ex
                self.logger.info("Server asked for a login. Trying to authenticate..")
                self._reniewsession()
            except InsuffAuthMedEx as ex:
                #  insufficient permissions for this reqeust would certainly cause the same problem again. So abort..
                raise
            except ConnectionMedEx as ex:
                #  connection related errors have a chance to recover. So give it another try..
                last_ex = ex
                self.logger.warn("Error while executing the remote call: ", exc_info=True)
                time.sleep(self.wait_after_error)
            except ServerProcessingMedEx:
                # this happends most likely due to wrong arguments passed to the server. So it would most
                # likely happen again.
                raise
            except MedastoException:
                # raised due to NON-2xx response status codes which have'n been recognized so far.
                raise
            finally:
                tries += 1
            # all other Exceptions that haven't been caught should abort immediatelly because we don't know whether
            # successive tries can succeed.

        # so loop finished either because self.isCancel was set to true or self.maxtriesiferror was reached.
        if last_ex is not None:
            # Giving up by rethrowing the last exception..
            raise last_ex

    def _dorequest(self, url, method='GET', body=None, contenttype='application/json', accept='application/json',
                   extra_headers=None, decode_response=True):
        try:
            headers = self._headers_default_and_custom(extra_headers, contenttype, accept)
            conns = self._connection()
            rel_url = self._relbaseurl() + url
            conns.request(method, rel_url, body, headers)
            res = conns.getresponse()
            self._check_httpstatuscode(res)  # raises Exceptions
            if decode_response:
                return res.read().decode(encoding='UTF-8')
            else:
                return res.read()

        except http.client.HTTPException as ex:
            raise ConnectionMedEx from ex
        except (ServerProcessingMedEx, PleaseAuthenticateMedEx, InsuffAuthMedEx, MedastoException):
            raise
        finally:
            if conns is not None:
                conns.close()

    def download(self, url, filepath, method='GET', body=None, contenttype='application/json',
                 accept='application/json, application/octet-stream', extra_headers=None):

        tries = 0
        last_ex = None
        while (tries < self.max_tries_on_error) and (not self.iscancel):
            try:
                self._dodownload(url, filepath, method, body, contenttype, accept, extra_headers)
                return

            except PleaseAuthenticateMedEx as ex:
                #  login + select project + try again
                last_ex = ex
                self.logger.info("Server asked for a login. Trying to authenticate..")
                self._reniewsession()
            except InsuffAuthMedEx:
                #  insufficient permissions for this reqeust would certainly cause the same problem again. So abort..
                raise
            except ConnectionMedEx as ex:
                #  connection related errors have a chance to recover. So give it another try..
                last_ex = ex
                self.logger.warn("Error while executing the remote call: ", exc_info=True)
                time.sleep(self.wait_after_error)
            except ServerProcessingMedEx:
                # this happends most likely due to wrong arguments passed to the server. So it would most
                # likely happen again.
                raise
            except MedastoException:
                # raised due to NON-2xx response status codes which have'n been recognized so far.
                raise
            finally:
                tries += 1
            # all other Exceptions that haven't been caught should abort immediatelly. This could be for example a
            # filesystem IO Error which will very likely not recover the next time.

        # so loop finished either because self.isCancel was set to true or self.maxtriesiferror was reached.
        if last_ex is not None:
            # Giving up by rethrowing the last exception..
            raise last_ex

    def _dodownload(self, url, filepath, method='GET', body=None, contenttype='application/json',
                    accept='application/json, application/octet-stream', extra_headers=None):
        try:
            headers = self._headers_default_and_custom(extra_headers, contenttype, accept)
            conns = self._connection()
            rel_url = self._relbaseurl() + url
            conns.request(method, rel_url, body, headers)
            res = conns.getresponse()
            self._check_httpstatuscode(res)  # raises Exceptions
            try:
                with open(filepath, 'xb') as file:
                    shutil.copyfileobj(res, file)
            except:
                self._removefilequietly(filepath)
                raise

        except http.client.HTTPException as ex:
            raise ConnectionMedEx from ex
        except (ServerProcessingMedEx, PleaseAuthenticateMedEx, InsuffAuthMedEx, MedastoException):
            raise
        finally:
            conns.close()

    def _headers_default_and_custom(self, custom_headers, contenttype, accept):
        headers = {"Authorization": "Session " + self._sessionid, "Content-Type": contenttype, "Accept": accept}
        if custom_headers is not None:
            headers.update(custom_headers)
        return headers

    def _check_httpstatuscode(self, httpresponse):
        """Raises different Exceptions on status code 299 and above. """
        # custom status codes..
        #     260: 'HTTP_CODE_AUTHENTICATION_ACCEPTED'
        #
        #     460: 'HTTP_CODE_PLEASE_AUTHENTICATE'
        #     462: 'HTTP_CODE_BAD_CREDENTIALS'          # only possible when trying to login
        #     463: 'HTTP_CODE_INSUFF_AUTH'
        #     464: 'HTTP_CODE_USERSESSIONS_EXCEEDED     # only possible when trying to login
        if httpresponse.status >= 299:
            if httpresponse.status == 299:
                resbytes = httpresponse.read()
                resstr = resbytes.decode(encoding='UTF-8')
                resjsonobj = json.loads(resstr)
                errormsg = resjsonobj['ERROR']
                raise ServerProcessingMedEx(errormsg)
            elif httpresponse.status == 460:
                raise PleaseAuthenticateMedEx
            elif httpresponse.status == 463:
                raise InsuffAuthMedEx
            else:  # try again..
                raise MedastoException(
                    "Bad Statuscode (" + str(httpresponse.status) + ") of http request: " + httpresponse.geturl())

    def _connection(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        context.verify_mode = ssl.CERT_NONE
        context.check_hostname = False
        return http.client.HTTPSConnection(self.serverurl, context=context)

    def _relbaseurl(self):
        return "/" + self.customerid + "/" + self._API_CONTEXT + "/"

    def url_from_args(self, *args, sep="/"):
        url = ""
        for arg in args:
            if isinstance(arg, str):
                url = (url + arg + sep)
            else:
                url = (url + str(arg) + sep)
        return url

    def select_project(self, projectid):
        try:
            url = self.url_from_args("project-select", projectid)
            self.request(url)
        except MedastoException:
            raise
        else:
            self.current_projectid = projectid

    def _removefilequietly(self, filepath):
        """Never raises Exceptions. Tries to delete the given filepath. """
        if filepath is not None:
            try:
                os.remove(filepath)
            except:
                self.logger.info("Error while cleaning up a file quietly.", exc_info=True)


class MedastoException(Exception):
    # Subclasses that define an __init__ must call Exception.__init__
    # or define self.args.  Otherwise, str() will fail.
    pass


class BadCredentialsMedEx(MedastoException):
    pass


class UserSessionsExceededMedEx(MedastoException):
    pass


class PleaseAuthenticateMedEx(MedastoException):
    pass


class InsuffAuthMedEx(MedastoException):
    pass


class ServerProcessingMedEx(MedastoException):
    pass


class ConnectionMedEx(MedastoException):
    pass


class ConnectionMedEx(MedastoException):
    pass


