from aiohttp_session import get_session
from .ticket_auth import TktAuthentication


class SessionTktAuthentication(TktAuthentication):
    """Ticket authentication mechanism based on the ticket_auth library, with
    ticket data being stored in the aiohttp_session object.
    """

    async def remember_ticket(self, request, ticket):
        """Called to store and remember the ticket data for a request"""
        session = await get_session(request)
        session[self.cookie_name] = ticket

    async def forget_ticket(self, request):
        """Called to forget the userid fro a request"""
        session = await get_session(request)
        session.pop(self.cookie_name, '')

    async def get_ticket(self, request):
        """Returns the userid for a request, or None if the request is not
        authenticated
        """
        session = await get_session(request)
        return session.get(self.cookie_name)
