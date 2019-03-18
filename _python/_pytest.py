#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All python-testing related details"
class PyTesting:
    "All python-testing related details"
    TEST  = 'pytest'
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
            "--coverage",
            help    = "Run tests with coverage",
            default = False,
            dest    = "TEST_COV",
            action  = "store_true",
        )
        grp.add_option(
            "--coverage",
            help    = "Create coverage",
            default = True,
            dest    = "TEST_COV",
            action  = "store_true",
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
        if _.options.TEST_HEADLESS:
            os.environ['DPX_TEST_HEADLESS'] = 'True'
            import_module("tests.testutils.bokehtesting").HEADLESS = True

        cmd = ["tests/", *_.options.TEST_GROUP]
        if not _.options.TEST_COV:
            import_module(cls.TEST).cmdline.main(cmd)
        else:
            cmd   = ["run", *cls.OMITS, "-m", cls.TEST] + cmd
            import_module(cls.COV).main(cmd)
            if not Path(cls.HTML).exists():
                os.mkdir(cls.HTML)
            import_module(cls.COV).main(["html", "-i", *cls.OMITS, "-d", cls.HTML])

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
