import ssl
import certifi
from django.core.mail.backends.smtp import EmailBackend

class CustomEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False

        connection_params = {
            "host": self.host,
            "port": self.port,
            "timeout": self.timeout,
        }

        self.connection = self.connection_class(**connection_params)

        if self.use_tls:
            context = ssl.create_default_context(cafile=certifi.where())
            self.connection.starttls(context=context)

        if self.username and self.password:
            self.connection.login(self.username, self.password)
        return True
