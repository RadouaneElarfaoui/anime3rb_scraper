from setuptools import setup, find_packages

setup(
    name='anime3rb_downloader',
    version='0.1.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    install_requires=[
        'cloudscraper',
        'BeautifulSoup4',
        'requests',
        'tqdm',
        'gradio',
    ],
    entry_points={
        'console_scripts': [
            'anime3rb_dl=anime3rb_downloader.cli_downloader:main',
        ],
    },
    author='Radouane Elarfaoui',
    description='A command-line utility and GUI application for scraping anime information and downloading episodes from anime3rb.com.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/RadouaneElarfaoui/anime3rb_scraper',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
