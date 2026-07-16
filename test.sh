#!/bin/sh
# Compiles and runs the Java test suite (test/) against the main source
# (src/), using the same lib/ jars as scripts/*/compile.sh plus JUnit's
# standalone console launcher (lib/junit-platform-console-standalone-*.jar).
#
# Usage: ./test.sh   (from the EdgeCloudSim/ repo root)
set -e

root="$(dirname "$(readlink -f "$0")")"
cd "$root"

junit_jar=$(ls lib/junit-platform-console-standalone-*.jar | head -n 1)

rm -rf bin test-bin
mkdir -p bin test-bin

echo "Compiling main source..."
javac -classpath "lib/cloudsim-4.0.jar:lib/commons-math3-3.6.1.jar:lib/colt.jar" \
	-sourcepath src \
	src/edu/boun/edgecloudsim/applications/resaco/ReSACOMainApp.java \
	-d bin

echo "Compiling tests..."
javac -classpath "bin:lib/cloudsim-4.0.jar:lib/commons-math3-3.6.1.jar:lib/colt.jar:${junit_jar}" \
	-sourcepath "src:test" \
	$(find test -name "*.java") \
	-d test-bin

echo "Running tests..."
java -jar "${junit_jar}" execute \
	--classpath "bin:test-bin:lib/cloudsim-4.0.jar:lib/commons-math3-3.6.1.jar:lib/colt.jar" \
	--scan-classpath test-bin
