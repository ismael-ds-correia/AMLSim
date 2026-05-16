package amlsim;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

import org.json.JSONObject;
import org.yaml.snakeyaml.Yaml;


/**
 * Simulation properties and global parameters loaded from the configuration JSON file
 */
public class SimProperties {

    private static final String separator = File.separator;
    private JSONObject generalProp;
    private JSONObject simProp;
    private JSONObject inputProp;
    private JSONObject outputProp;
    private JSONObject cashInProp;
    private JSONObject cashOutProp;
    private String workDir;
    private double marginRatio;  // Ratio of margin for AML typology transactions
    private int seed;  // Seed of randomness
    private String simName;  // Simulation name

    private int normalTxInterval;
    private double minTxAmount;  // Minimum base (normal) transaction amount
    private double maxTxAmount;  // Maximum base (suspicious) transaction amount
    private Integer stepsOverride = null;
    private String outputDirOverride = null;

    // YAML-only overrides for fragmented typologies (JSON remains the source for existing settings)
    private double fragmentedLegalLimit = 6000.0;
    private double fragmentedMaxTotal = 20000.0;
    private int fragmentedMinCycles = 3;
    private int fragmentedMaxCycles = 40;
    private double fragmentedMinFrac = 0.0007;
    private double fragmentedMaxFrac = 0.030;
    private double fragmentedAlphaFrac = 2.7;
    private double fragmentedAlphaDay = 1.6;
    private double fragmentedCycleAlpha = 1.5;
    private int fragmentedMinWindow = 3;
    private int fragmentedMaxWindow = 15;
    private double fragmentedAlphaWindow = 1.5;
    private double fragmentedDepositMinDay = 800.0;
    private double fragmentedDepositMaxDay = 50000.0;
    private double fragmentedWithdrawalMinDay = -50000.0;
    private double fragmentedWithdrawalMaxDay = -800.0;

    SimProperties(String jsonName) throws IOException{
        String jsonStr = loadTextFile(jsonName);
        JSONObject jsonObject = new JSONObject(jsonStr);
        JSONObject defaultProp = jsonObject.getJSONObject("default");

        generalProp = jsonObject.getJSONObject("general");
        simProp = jsonObject.getJSONObject("simulator");
        inputProp = jsonObject.getJSONObject("temporal");  // Input directory of this simulator is temporal directory
        outputProp = jsonObject.getJSONObject("output");

        normalTxInterval = simProp.getInt("transaction_interval");
        minTxAmount = defaultProp.getDouble("min_amount");
        maxTxAmount = defaultProp.getDouble("max_amount");

        System.out.printf("General transaction interval: %d\n", normalTxInterval);
        System.out.printf("Base transaction amount: Normal = %f, Suspicious= %f\n", minTxAmount, maxTxAmount);
        
        cashInProp = defaultProp.getJSONObject("cash_in");
        cashOutProp = defaultProp.getJSONObject("cash_out");
        marginRatio = defaultProp.getDouble("margin_ratio");

        String envSeed = System.getenv("RANDOM_SEED");
        boolean seedLockedByEnv = envSeed != null;
        seed = seedLockedByEnv ? Integer.parseInt(envSeed) : generalProp.getInt("random_seed");

        String simNameBySystem = System.getProperty("simulation_name");
        boolean simNameLockedBySystem = simNameBySystem != null && !simNameBySystem.trim().isEmpty();
        simName = simNameLockedBySystem ? simNameBySystem : generalProp.getString("simulation_name");

        loadYamlConfig(seedLockedByEnv, simNameLockedBySystem);

        System.out.println("Random seed: " + seed);
        System.out.println("Simulation name: " + simName);

        workDir = inputProp.getString("directory") + separator + simName + separator;
        System.out.println("Working directory: " + workDir);
    }

    private void loadYamlConfig(boolean seedLockedByEnv, boolean simNameLockedBySystem) {
        String yamlPath = System.getProperty("fragmented.config", "config.yaml");
        Path path = Paths.get(yamlPath);
        if (!Files.exists(path)) {
            System.out.println("YAML config not found, using JSON/defaults: " + path.toAbsolutePath());
            return;
        }

        try (InputStream inputStream = Files.newInputStream(path)) {
            Yaml yaml = new Yaml();
            Object loaded = yaml.load(inputStream);
            if (!(loaded instanceof Map)) {
                throw new IllegalArgumentException("Invalid YAML root format: expected a mapping at " + path.toAbsolutePath());
            }

            Map<?, ?> root = (Map<?, ?>) loaded;
            Map<?, ?> simulation = getMap(root, "simulation");
            if (simulation != null) {
                Integer yamlSteps = getOptionalInt(simulation, "total_steps");
                if (yamlSteps != null) {
                    if (yamlSteps > 0) {
                        stepsOverride = yamlSteps;
                    } else {
                        throw new IllegalArgumentException("Invalid YAML simulation.total_steps: must be > 0");
                    }
                }

                Integer yamlSeed = getOptionalInt(simulation, "seed");
                if (yamlSeed != null) {
                    if (!seedLockedByEnv) {
                        seed = yamlSeed;
                    } else {
                        System.out.println("YAML simulation.seed ignored because RANDOM_SEED environment variable is set.");
                    }
                }

                String yamlSimName = getOptionalString(simulation, "simulation_name", "name");
                if (yamlSimName != null) {
                    if (!simNameLockedBySystem) {
                        simName = yamlSimName;
                    } else {
                        System.out.println("YAML simulation name ignored because -Dsimulation_name is set.");
                    }
                }

                String yamlOutputDir = getOptionalString(simulation, "output_dir");
                if (yamlOutputDir != null) {
                    outputDirOverride = yamlOutputDir;
                }
            }

            Map<?, ?> yamlTransactions = getMap(root, "transactions");
            if (yamlTransactions != null) {
                Double yamlMinAmount = getOptionalDouble(yamlTransactions, "min_amount");
                Double yamlMaxAmount = getOptionalDouble(yamlTransactions, "max_amount");
                if (yamlMinAmount != null && yamlMinAmount > 0.0) {
                    minTxAmount = yamlMinAmount;
                } else if (yamlMinAmount != null) {
                    throw new IllegalArgumentException("Invalid YAML transactions.min_amount: must be > 0");
                }
                if (yamlMaxAmount != null && yamlMaxAmount >= minTxAmount) {
                    maxTxAmount = yamlMaxAmount;
                } else if (yamlMaxAmount != null) {
                    throw new IllegalArgumentException("Invalid YAML transactions.max_amount: must be >= transactions.min_amount");
                }
            }

            Map<?, ?> transactions = getMap(root, "transactions");
            if (transactions == null) {
                throw new IllegalArgumentException("Missing required YAML section 'transactions'");
            }

            Double yamlLegalLimit = getOptionalDouble(transactions, "LEGAL_LIMIT", "legal_limit");
            if (yamlLegalLimit != null) {
                if (yamlLegalLimit > 0.0) {
                    fragmentedLegalLimit = yamlLegalLimit;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.LEGAL_LIMIT: must be > 0");
                }
            }

            Double yamlMaxTotal = getOptionalDouble(transactions, "MAX_TOTAL", "max_total");
            if (yamlMaxTotal != null) {
                if (yamlMaxTotal > 0.0) {
                    fragmentedMaxTotal = yamlMaxTotal;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.MAX_TOTAL: must be > 0");
                }
            }

            Integer yamlMinCycles = getOptionalInt(transactions, "minCycles", "min_cycles");
            if (yamlMinCycles != null) {
                if (yamlMinCycles > 0) {
                    fragmentedMinCycles = yamlMinCycles;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.minCycles: must be > 0");
                }
            }

            Integer yamlMaxCycles = getOptionalInt(transactions, "maxCycles", "max_cycles");
            if (yamlMaxCycles != null) {
                if (yamlMaxCycles >= fragmentedMinCycles) {
                    fragmentedMaxCycles = yamlMaxCycles;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.maxCycles: must be >= minCycles");
                }
            }

            Double yamlMinFrac = getOptionalDouble(transactions, "minFrac", "min_frac");
            if (yamlMinFrac != null) {
                if (yamlMinFrac > 0.0) {
                    fragmentedMinFrac = yamlMinFrac;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.minFrac: must be > 0");
                }
            }

            Double yamlMaxFrac = getOptionalDouble(transactions, "maxFrac", "max_frac");
            if (yamlMaxFrac != null) {
                if (yamlMaxFrac >= fragmentedMinFrac) {
                    fragmentedMaxFrac = yamlMaxFrac;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.maxFrac: must be >= minFrac");
                }
            }

            Double yamlAlphaFrac = getOptionalDouble(transactions, "alphaFrac", "alpha_frac");
            if (yamlAlphaFrac != null) {
                if (yamlAlphaFrac > 0.0) {
                    fragmentedAlphaFrac = yamlAlphaFrac;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.alphaFrac: must be > 0");
                }
            }

            Double yamlAlphaDay = getOptionalDouble(transactions, "alphaDay", "alpha_day");
            if (yamlAlphaDay != null) {
                if (yamlAlphaDay > 0.0) {
                    fragmentedAlphaDay = yamlAlphaDay;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.alphaDay: must be > 0");
                }
            }

            Double yamlCycleAlpha = getOptionalDouble(transactions, "cycleAlpha", "cycle_alpha");
            if (yamlCycleAlpha != null) {
                if (yamlCycleAlpha > 0.0) {
                    fragmentedCycleAlpha = yamlCycleAlpha;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.cycleAlpha: must be > 0");
                }
            }

            Integer yamlMinWindow = getOptionalInt(transactions, "minWindow", "min_window");
            if (yamlMinWindow != null) {
                if (yamlMinWindow > 0) {
                    fragmentedMinWindow = yamlMinWindow;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.minWindow: must be > 0");
                }
            }

            Integer yamlMaxWindow = getOptionalInt(transactions, "maxWindow", "max_window");
            if (yamlMaxWindow != null) {
                if (yamlMaxWindow >= fragmentedMinWindow) {
                    fragmentedMaxWindow = yamlMaxWindow;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.maxWindow: must be >= minWindow");
                }
            }

            Double yamlAlphaWindow = getOptionalDouble(transactions, "alphaWindow", "alpha_window");
            if (yamlAlphaWindow != null) {
                if (yamlAlphaWindow > 0.0) {
                    fragmentedAlphaWindow = yamlAlphaWindow;
                } else {
                    throw new IllegalArgumentException("Invalid YAML transactions.alphaWindow: must be > 0");
                }
            }

            // Optional type-specific overrides
            Map<?, ?> fragmentedDeposit = getMap(transactions, "fragmented_deposit");
            if (fragmentedDeposit != null) {
                Double yamlDepositMinDay = getOptionalDouble(fragmentedDeposit, "minDay", "min_day");
                if (yamlDepositMinDay != null) {
                    if (yamlDepositMinDay > 0.0) {
                        fragmentedDepositMinDay = yamlDepositMinDay;
                    } else {
                        throw new IllegalArgumentException("Invalid YAML transactions.fragmented_deposit.minDay: must be > 0");
                    }
                }

                Double yamlDepositMaxDay = getOptionalDouble(fragmentedDeposit, "maxDay", "max_day");
                if (yamlDepositMaxDay != null) {
                    if (yamlDepositMaxDay >= fragmentedDepositMinDay) {
                        fragmentedDepositMaxDay = yamlDepositMaxDay;
                    } else {
                        throw new IllegalArgumentException("Invalid YAML transactions.fragmented_deposit.maxDay: must be >= minDay");
                    }
                }
            }

            Map<?, ?> fragmentedWithdrawal = getMap(transactions, "fragmented_withdrawal");
            if (fragmentedWithdrawal != null) {
                Double yamlWithdrawalMinDay = getOptionalDouble(fragmentedWithdrawal, "minDay", "min_day");
                if (yamlWithdrawalMinDay != null) {
                    if (yamlWithdrawalMinDay < 0.0) {
                        fragmentedWithdrawalMinDay = yamlWithdrawalMinDay;
                    } else {
                        throw new IllegalArgumentException("Invalid YAML transactions.fragmented_withdrawal.minDay: must be negative");
                    }
                }

                Double yamlWithdrawalMaxDay = getOptionalDouble(fragmentedWithdrawal, "maxDay", "max_day");
                if (yamlWithdrawalMaxDay != null) {
                    if (yamlWithdrawalMaxDay <= fragmentedWithdrawalMinDay) {
                        fragmentedWithdrawalMaxDay = yamlWithdrawalMaxDay;
                    } else {
                        throw new IllegalArgumentException("Invalid YAML transactions.fragmented_withdrawal.maxDay: must be <= minDay");
                    }
                }
            }

            System.out.printf(
                    "YAML loaded from %s (steps=%s, seed=%d, simName=%s, outputDir=%s, minAmount=%.2f, maxAmount=%.2f, LEGAL_LIMIT=%.2f, minFrac=%.6f, maxFrac=%.6f)%n",
                    path.toAbsolutePath(),
                    stepsOverride == null ? "JSON" : stepsOverride.toString(),
                    seed,
                    simName,
                    outputDirOverride == null ? "JSON" : outputDirOverride,
                    minTxAmount,
                    maxTxAmount,
                    fragmentedLegalLimit,
                    fragmentedMinFrac,
                    fragmentedMaxFrac
            );
        } catch (Exception e) {
            throw new IllegalArgumentException("Failed to load YAML config: " + path.toAbsolutePath(), e);
        }
    }

    private static Map<?, ?> getMap(Map<?, ?> source, String key) {
        Object value = source.get(key);
        if (value instanceof Map) {
            return (Map<?, ?>) value;
        }
        return null;
    }

    private static double getDouble(Map<?, ?> source, double defaultValue, String... keys) {
        for (String key : keys) {
            Object value = source.get(key);
            if (value instanceof Number) {
                return ((Number) value).doubleValue();
            }
        }
        return defaultValue;
    }

    private static int getInt(Map<?, ?> source, int defaultValue, String... keys) {
        for (String key : keys) {
            Object value = source.get(key);
            if (value instanceof Number) {
                return ((Number) value).intValue();
            }
        }
        return defaultValue;
    }

    private static Integer getOptionalInt(Map<?, ?> source, String... keys) {
        for (String key : keys) {
            Object value = source.get(key);
            if (value instanceof Number) {
                return ((Number) value).intValue();
            }
            if (value != null) {
                throw new IllegalArgumentException("Invalid YAML value for '" + key + "': expected integer");
            }
        }
        return null;
    }

    private static Double getOptionalDouble(Map<?, ?> source, String... keys) {
        for (String key : keys) {
            Object value = source.get(key);
            if (value instanceof Number) {
                return ((Number) value).doubleValue();
            }
            if (value != null) {
                throw new IllegalArgumentException("Invalid YAML value for '" + key + "': expected number");
            }
        }
        return null;
    }

    private static String getOptionalString(Map<?, ?> source, String... keys) {
        for (String key : keys) {
            Object value = source.get(key);
            if (value instanceof String) {
                String text = ((String) value).trim();
                if (!text.isEmpty()) {
                    return text;
                }
                throw new IllegalArgumentException("Invalid YAML value for '" + key + "': expected non-empty string");
            }
            if (value != null) {
                throw new IllegalArgumentException("Invalid YAML value for '" + key + "': expected string");
            }
        }
        return null;
    }

    private static String loadTextFile(String jsonName) throws IOException{
        Path file = Paths.get(jsonName);
        byte[] bytes = Files.readAllBytes(file);
        return new String(bytes);
    }

    String getSimName(){
        return simName;
    }

    public int getSeed(){
        return seed;
    }

    public int getSteps(){
        return stepsOverride != null ? stepsOverride.intValue() : generalProp.getInt("total_steps");
    }

    boolean isComputeDiameter(){
        return simProp.getBoolean("compute_diameter");
    }

    int getTransactionLimit(){
        return simProp.getInt("transaction_limit");
    }

    int getNormalTransactionInterval(){
        return normalTxInterval;
    }

    public double getMinTransactionAmount() {
        return minTxAmount;
    }

    public double getMaxTransactionAmount() {
        return maxTxAmount;
    }

    public double getMarginRatio(){
        return marginRatio;
    }

    int getNumBranches(){
        return simProp.getInt("numBranches");
    }

    String getInputAcctFile(){
        return workDir + inputProp.getString("accounts");
    }

    String getInputTxFile(){
        return workDir + inputProp.getString("transactions");
    }

    String getInputAlertMemberFile() {
        return workDir + inputProp.getString("alert_members");
    }

    String getNormalModelsFile() {
        return workDir + inputProp.getString("normal_models");
    }

    String getOutputTxLogFile(){
        return getOutputDir() + outputProp.getString("transaction_log");
    }

    String getOutputDir(){
        if (outputDirOverride != null) {
            return outputDirOverride.endsWith(separator) ? outputDirOverride : outputDirOverride + separator;
        }
        return outputProp.getString("directory") + separator + simName + separator;
    }

    String getCounterLogFile(){
        return getOutputDir() + outputProp.getString("counter_log");
    }

    String getDiameterLogFile(){
        return workDir + outputProp.getString("diameter_log");
    }

    int getCashTxInterval(boolean isCashIn, boolean isSAR){
        String key = isSAR ? "fraud_interval" : "normal_interval";
        return isCashIn ? cashInProp.getInt(key) : cashOutProp.getInt(key);
    }

    float getCashTxMinAmount(boolean isCashIn, boolean isSAR){
        String key = isSAR ? "fraud_min_amount" : "normal_min_amount";
        return isCashIn ? cashInProp.getFloat(key) : cashOutProp.getFloat(key);
    }

    float getCashTxMaxAmount(boolean isCashIn, boolean isSAR){
        String key = isSAR ? "fraud_max_amount" : "normal_max_amount";
        return isCashIn ? cashInProp.getFloat(key) : cashOutProp.getFloat(key);
    }

    public double getFragmentedLegalLimit() {
        return fragmentedLegalLimit;
    }

    public double getFragmentedMaxTotal() {
        return fragmentedMaxTotal;
    }

    public int getFragmentedMinCycles() {
        return fragmentedMinCycles;
    }

    public int getFragmentedMaxCycles() {
        return fragmentedMaxCycles;
    }

    public double getFragmentedMinFrac() {
        return fragmentedMinFrac;
    }

    public double getFragmentedMaxFrac() {
        return fragmentedMaxFrac;
    }

    public double getFragmentedAlphaFrac() {
        return fragmentedAlphaFrac;
    }

    public double getFragmentedAlphaDay() {
        return fragmentedAlphaDay;
    }

    public double getFragmentedCycleAlpha() {
        return fragmentedCycleAlpha;
    }

    public int getFragmentedMinWindow() {
        return fragmentedMinWindow;
    }

    public int getFragmentedMaxWindow() {
        return fragmentedMaxWindow;
    }

    public double getFragmentedAlphaWindow() {
        return fragmentedAlphaWindow;
    }

    public double getFragmentedDepositMinDay() {
        return fragmentedDepositMinDay;
    }

    public double getFragmentedDepositMaxDay() {
        return fragmentedDepositMaxDay;
    }

    public double getFragmentedWithdrawalMinDay() {
        return fragmentedWithdrawalMinDay;
    }

    public double getFragmentedWithdrawalMaxDay() {
        return fragmentedWithdrawalMaxDay;
    }
}


