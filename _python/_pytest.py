#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All python-testing related details"
def _run(cov, args):
    from   importlib import import_module
    import_module(cov).main(args)

class PyTesting:
    "All python-testing related details"
    TEST    = 'pytest'
    OPTS    = ["--tb", "short"]
    COV     = 'coverage.cmdline'
    OMITS   = ["--omit", 'tests/*.py,*waf*.py,*test*.py']
    HTML    = "Coverage"
    CAPTURE = "lcov --capture --directory ./ --output-file {output}"
    REMOVE  = "lcov --remove {input} \"*/include/*\" --output-file {output}"
    GENHTML = "genhtml {input} --output-directory {output}"
    INDEX   = """
        <!DOCTYPE HTML PUBLIC>
        <html lang='en'>
            <head>
                <meta http-equiv='Content-Type' content='text/html; charset=UTF-8'>
                <title>Code Coverage</title>
            </head>
            <body>
                <iframe src="Cpp/index.html" width='100%' height='500px'></iframe>
                <iframe src="Python/index.html" width='100%' height='500px'></iframe>
            </body>
        </html>
        """
    @staticmethod
    def options(ctx):
        "add options"
        grp = ctx.add_option_group('Test options')
        for j, k in [
                ('integration', ('-m', 'integration')),
                ('unit',        ('-m', 'not integration')),
                ('all',         ())
        ]:
            grp.add_option(
                f'-{j[0]}', f'--{j}tests',
                help    = f"Run {j} tests",
                default = ("-m", "not integration"),
                dest    = "TEST_GROUP",
                action  = "store_const",
                const   = k
            )
        grp.add_option(
            "--pv",
            help    = f"verbose output",
            dest    = "PYTEST_V",
            default = False,
            action  = "store_true",
        )
        grp.add_option(
            "--junit",
            help    = f"Create a junit xml report at the provided path",
            dest    = "JUNIT_XML",
        )
        grp.add_option(
            "--coverage",
            help    = "Run tests with coverage",
            dest    = "TEST_COV",
        )
        grp.add_option(
            "--noheadless",
            help    = "Run browsers in without headless mode",
            default = True,
            dest    = "TEST_HEADLESS",
            action  = "store_false",
        )

    @classmethod
    def test(cls, bld):
        "do unit tests"
        import os
        from   pathlib   import Path
        from   importlib import import_module
        from   waflib.Logs   import info
        info(
            "Using CONDA_DEFAULT_ENV: %s",
            os.environ.get('CONDA_DEFAULT_ENV', '-')
        )
        info("Path to os module: %s", os.__file__)
        os.chdir("build")
        opt = bld.options
        if opt.TEST_HEADLESS:
            os.environ['DPX_TEST_HEADLESS'] = 'True'

        junit = () if not opt.JUNIT_XML else ('--junit-xml', opt.JUNIT_XML)
        cmd   = ["tests", *opt.TEST_GROUP, *junit, *cls.OPTS]
        if opt.PYTEST_V:
            cmd.append("-v")
        if not opt.TEST_COV:
            import_module(cls.TEST).cmdline.main(cmd)
            return

        for i in Path(".").glob("./**/*.gcda"):
            i.unlink()

        import_module(cls.COV).main(["run", *cls.OMITS, "-m", cls.TEST, *cmd])

    @classmethod
    def html(cls, bld):
        "create the html"
        import os
        from   pathlib   import Path
        from   importlib import import_module
        from   waflib.Logs   import info
        os.chdir("build")
        opt  = bld.options
        gcda = any(Path(".").glob("./**/*.gcda"))
        info("Found gcda files at %s: %s", Path(".").resolve(), gcda)
        Path(opt.TEST_COV).mkdir(parents = True, exist_ok = True)
        out = opt.TEST_COV + ('/Python' if gcda else '')
        import_module(cls.COV).main(["html", "-i", *cls.OMITS, "-d", out])
        if gcda:
            cls.__lcov(bld)

    @classmethod
    def make(cls, locs):
        "add the options & test"
        def options(ctx, __old__ = locs.pop('options')):
            __old__(ctx)
            cls.options(ctx)

        locs.update(
            options = options,
            test    = cls.test,
            html    = cls.html
        )

    @classmethod
    def __lcov(cls, bld):
        "create lcov report"
        cwd = "build"
        opt = bld.options
        bld.cmd_and_log(
            cls.CAPTURE.format(output = "cppcoverage.info"),
            cwd = cwd
        )
        bld.cmd_and_log(
            cls.REMOVE.format(input  = "cppcoverage.info", output = "cppfiltered.info"),
            cwd = cwd
        )
        bld.cmd_and_log(
            cls.GENHTML.format(input  = "cppfiltered.info", output = opt.TEST_COV+"/Cpp"),
            cwd = cwd
        )
        with open(opt.TEST_COV+"/index.html", "w", encoding = "utf-8") as stream:
            print(cls.INDEX, file = stream)
