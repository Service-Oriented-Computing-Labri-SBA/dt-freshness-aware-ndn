# Contributing

Contributions that improve reproducibility, compatibility, documentation, or experimental coverage are welcome.

Before submitting a change:

1. run the environment checker;
2. rebuild ns-3/ndnSIM;
3. run `run_smoke_tests.sh`;
4. verify `Smoke validation PASS`;
5. describe any change to the experiment design or metric definition explicitly.

Please avoid silently changing default E1/E4 parameters in a way that makes new results incomparable with the published/released configuration.
