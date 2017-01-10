import pytest
import aiohttp_session
from aiohttp import web
from aiohttp_auth import acl, auth
from aiohttp_auth.permissions import Group, Permission
from utils import assert_response


@pytest.fixture
def app(loop):
    """Default app fixture for tests."""
    async def handler_remember(request):
        await auth.remember(request, 'some_user')
        return web.Response(text='remember')

    application = web.Application(loop=loop)

    secret = b'01234567890abcdef'
    storage = aiohttp_session.SimpleCookieStorage()
    policy = auth.SessionTktAuthentication(secret, 15, cookie_name='auth')

    aiohttp_session.setup(application, storage)
    auth.setup(application, policy)

    application.router.add_get('/remember', handler_remember)

    yield application


async def _groups_callback(user_id):
    """Groups callback function that always returns two groups."""
    return ('group0', 'group1')


async def _auth_groups_callback(user_id):
    """Groups callback function that always returns two groups."""
    if user_id:
        return ('group0', 'group1')

    return ()


async def _none_groups_callback(user_id):
    """Groups callback function that always returns None."""
    return None


async def test_acl_middleware_setup(app):
    acl.setup(app, _groups_callback)

    middleware = acl.acl_middleware(_groups_callback)

    assert app.middlewares[-1].__name__ == middleware.__name__


async def test_no_middleware_installed(app, client):
    async def handler_test(request):
        with pytest.raises(RuntimeError):
            await acl.get_user_groups(request)

        return web.Response(text='test')

    app.router.add_get('/test', handler_test)
    cli = await client(app)

    await assert_response(cli.get('/remember'), 'remember')

    await assert_response(cli.get('/test'), 'test')


async def test_correct_groups_returned_for_authenticated_user(app, client):
    async def handler_test(request):
        groups = await acl.get_user_groups(request)

        assert 'group0' in groups
        assert 'group1' in groups
        assert 'some_user' in groups
        assert Group.Everyone in groups
        assert Group.AuthenticatedUser in groups

        return web.Response(text='test')

    acl.setup(app, _groups_callback)
    app.router.add_get('/test', handler_test)

    cli = await client(app)

    await assert_response(cli.get('/remember'), 'remember')

    await assert_response(cli.get('/test'), 'test')


async def test_correct_groups_returned_for_unauthenticated_user(app, client):
    async def handler_test(request):
        groups = await acl.get_user_groups(request)

        assert 'group0' in groups
        assert 'group1' in groups
        assert 'some_user' not in groups
        assert Group.Everyone in groups
        assert Group.AuthenticatedUser not in groups

        return web.Response(text='test')

    acl.setup(app, _groups_callback)
    app.router.add_get('/test', handler_test)

    cli = await client(app)

    await assert_response(cli.get('/test'), 'test')


async def test_no_groups_if_none_returned_from_callback(app, client):
    async def handler_test(request):
        groups = await acl.get_user_groups(request)
        assert groups is None

        return web.Response(text='test')

    acl.setup(app, _none_groups_callback)
    app.router.add_get('/test', handler_test)

    cli = await client(app)

    await assert_response(cli.get('/test'), 'test')


async def test_acl_permissions(app, client):
    async def handler_test(request):
        context = [(Permission.Allow, 'group0', ('test0',)),
                   (Permission.Deny, 'group1', ('test1',)),
                   (Permission.Allow, Group.Everyone, ('test1',))]

        assert (await acl.get_permitted(request, 'test0', context)) is True
        assert (await acl.get_permitted(request, 'test1', context)) is False

        return web.Response(text='test')

    acl.setup(app, _groups_callback)
    app.router.add_get('/test', handler_test)

    cli = await client(app)

    await assert_response(cli.get('/test'), 'test')


async def test_permission_order(app, client):
    context = [(Permission.Allow, Group.Everyone, ('test0',)),
               (Permission.Deny, 'group1', ('test1',)),
               (Permission.Allow, Group.Everyone, ('test1',))]

    async def handler_test0(request):
        assert (await acl.get_permitted(request, 'test0', context)) is True
        assert (await acl.get_permitted(request, 'test1', context)) is False

        return web.Response(text='test0')

    async def handler_test1(request):
        assert (await acl.get_permitted(request, 'test0', context)) is True
        assert (await acl.get_permitted(request, 'test1', context)) is True

        return web.Response(text='test1')

    acl.setup(app, _auth_groups_callback)
    app.router.add_get('/test0', handler_test0)
    app.router.add_get('/test1', handler_test1)

    cli = await client(app)

    await assert_response(cli.get('/test1'), 'test1')
    await assert_response(cli.get('/remember'), 'remember')
    await assert_response(cli.get('/test0'), 'test0')