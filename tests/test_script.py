from subprocess import PIPE, CalledProcessError, run
from tempfile import TemporaryDirectory

from pytest import fixture, raises


@fixture(params=('roboversion', 'python -m roboversion'))
def roboversion_call(request):
	return request.param.split()


def test_failure(roboversion_call):
	with TemporaryDirectory() as tmp:
		arguments = *roboversion_call, tmp
		result = run(arguments, check=True, stdout=PIPE, stderr=PIPE)
	assert not result.stdout
	assert result.stderr
	with raises(CalledProcessError):
		run(arguments, check=True, stdout=PIPE, stderr=PIPE)
