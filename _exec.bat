cd @directory@;
SET PATH=%~dp0\\@directory@\\Library\\bin;%PATH%;
@start@ %~dp0\@directory@\@python@ -I @cmdline@ @scriptname@;
@pause@
