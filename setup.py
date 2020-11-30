from setuptools import setup
import versioneer

setup(
    name="reddit-stalker",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='Reddit streaming for your "following" users',
    url="github.com/mikeage/reddit_stalker",
    author="Mike Miller",
    author_email="github@mikeage.net",
    license="MIT",
    packages=["reddit_stalker"],
    entry_points={"console_scripts": ["reddit-stalker=reddit_stalker.stream:main"]},
    install_requires=["praw", "colorama", "dateparser"],
    zip_safe=False,
)
