#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All python-testing related details"
class PyTesting:
    "All python-testing related details"
    TEST  = 'pytest'
    OPTS  = ["--tb", "short"]
    COV   = 'coverage.cmdline'
    OMITS = ["--omit", 'tests/*.py,*waf*.py,*test*.py']
    HTML  = "Coverage"
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
    def test(cls, _):
        "do unit tests"
        import os
        from   pathlib   import Path
        from   importlib import import_module
        os.chdir("build")
        opt = _.options
        if opt.TEST_HEADLESS:
            os.environ['DPX_TEST_HEADLESS'] = 'True'

        junit = () if not opt.JUNIT_XML else ('--junit-xml', opt.JUNIT_XML)
        cmd   = ["tests/", *opt.TEST_GROUP, *junit, *cls.OPTS]
        if not opt.TEST_COV:
            import_module(cls.TEST).cmdline.main(cmd)
        else:
            import_module(cls.COV).main(["run", *cls.OMITS, "-m", cls.TEST, *cmd])
            Path(opt.TEST_COV).mkdir(parents = True, exist_ok = True)
            import_module(cls.COV).main(["html", "-i", *cls.OMITS, "-d", opt.TEST_COV])

    @classmethod
    def make(cls, locs):
        "add the options & test"
        def options(ctx, __old__ = locs.pop('options')):
            __old__(ctx)
            cls.options(ctx)

        locs.update(
            options = options,
            test    = cls.test
        )
