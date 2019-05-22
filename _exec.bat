cd @code@;
SET PATH=%~dp0\\@distrib@\\Library\\bin;%PATH%;
@start@ %~dp0\@distrib@\@python@ -I @cmdline@ @scriptname@;
@pause@
