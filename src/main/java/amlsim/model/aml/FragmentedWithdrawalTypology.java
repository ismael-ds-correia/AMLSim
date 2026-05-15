package amlsim.model.aml;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

import amlsim.AMLSim;
import amlsim.Account;
import amlsim.model.cash.CashOutModel;

/**
 * Fragmented Withdrawal Typology
 * Simula saques fracionados para mascarar valores acima do limite legal.
 */
public class FragmentedWithdrawalTypology extends AMLTypology {

    private Account targetAccount;                          // Conta que fará os saques
    private List<Long> withdrawalSteps = new ArrayList<>();     // Passos de simulação para cada saque
    private List<Double> withdrawalAmounts = new ArrayList<>(); // Valores de cada saque fracionado

    private Random random = AMLSim.getRandom();

    FragmentedWithdrawalTypology(double minAmount, double maxAmount, int startStep, int endStep) {
        super(minAmount, maxAmount, startStep, endStep);
    }

    @Override
    public void setParameters(int modelID) {
        targetAccount = alert.getMainAccount();
        if (targetAccount == null && !alert.getMembers().isEmpty()) {
            targetAccount = alert.getMembers().get(0);
        }

        withdrawalAmounts.clear();
        withdrawalSteps.clear();

        double legalLimit = AMLSim.getSimProp().getFragmentedLegalLimit();

        int minFrac = (int) Math.max(1, Math.round(AMLSim.getSimProp().getFragmentedMinFrac() * legalLimit));
        int maxFrac = (int) Math.max(1, Math.round(AMLSim.getSimProp().getFragmentedMaxFrac() * legalLimit));
        double alphaFrac = AMLSim.getSimProp().getFragmentedAlphaFrac();

        // Parâmetros da power law para o saldo líquido diário (negativos)
        double minDay = AMLSim.getSimProp().getFragmentedWithdrawalMinDay();
        double maxDay = AMLSim.getSimProp().getFragmentedWithdrawalMaxDay();
        double alphaDay = AMLSim.getSimProp().getFragmentedAlphaDay();

        int minCycles = AMLSim.getSimProp().getFragmentedMinCycles();
        int maxCycles = AMLSim.getSimProp().getFragmentedMaxCycles();
        int numCycles = samplePowerLaw(minCycles, maxCycles, AMLSim.getSimProp().getFragmentedCycleAlpha(), random);

        int minWindow = AMLSim.getSimProp().getFragmentedMinWindow();
        int maxWindow = AMLSim.getSimProp().getFragmentedMaxWindow();
        double alphaWindow = AMLSim.getSimProp().getFragmentedAlphaWindow();

        int usedStep = (int)startStep;

        for (int cycle = 0; cycle < numCycles; cycle++) {
            int windowSize = samplePowerLaw(minWindow, maxWindow, alphaWindow, random);

            if (usedStep + windowSize > endStep) {
                usedStep = (int)startStep;
            }
            long windowStart = usedStep;
            usedStep += windowSize;

            List<Long> windowDays = new ArrayList<>();
            for (int i = 0; i < windowSize; i++) {
                windowDays.add(windowStart + i);
            }

            // Para cada dia da janela, sorteia o valor diário pela power law (negativo)
            for (int i = 0; i < windowSize; i++) {
                double r = random.nextDouble();
                // Power law invertida para valores negativos
                double powMin = Math.pow(Math.abs(minDay), 1.0 - alphaDay);
                double powMax = Math.pow(Math.abs(maxDay), 1.0 - alphaDay);
                double value = Math.pow(powMin + r * (powMax - powMin), 1.0 / (1.0 - alphaDay));
                value = -value; // Garante valor negativo

                // Fragmenta o valor diário em frações menores (também por power law)
                double withdrawn = 0.0;
                List<Double> frags = new ArrayList<>();
                while (withdrawn < Math.abs(value)) {
                    int fraction = samplePowerLaw(minFrac, maxFrac, alphaFrac, random);
                    double remaining = Math.abs(value) - withdrawn;
                    double withdrawalValue = Math.min(fraction, remaining);
                    frags.add(withdrawalValue);
                    withdrawn += withdrawalValue;
                }
                for (double val : frags) {
                    withdrawalAmounts.add(val);
                    withdrawalSteps.add(windowDays.get(i));
                }
            }
        }
    }

    @Override
    public String getModelName() {
        return "FragmentedWithdrawalTypology";
    }
    
    @Override
    public void sendTransactions(long step, Account acct) {
        if (!acct.getID().equals(targetAccount.getID())) {
            return;
        }
        for (int i = 0; i < withdrawalSteps.size(); i++) {
            if (withdrawalSteps.get(i) == step) {
                double amount = withdrawalAmounts.get(i);

                // Realiza o saque usando o modelo de cash-out
                CashOutModel cashOut = acct.getCashOutModel();
                cashOut.registerExternalWithdrawal(step, amount, "FRAGMENTED_WITHDRAWAL", alert.getAlertID());
            }
        }
    }
}