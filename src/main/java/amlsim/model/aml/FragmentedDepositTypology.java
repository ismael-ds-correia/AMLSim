package amlsim.model.aml;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

import amlsim.AMLSim;
import amlsim.Account;
import amlsim.model.cash.CashCheckDepositModel;
import amlsim.model.cash.CashDepositModel;

/**
 * Fragmented Deposit Typology
 * Simula depósitos fracionados para mascarar valores acima do limite legal.
 */
public class FragmentedDepositTypology extends AMLTypology {

    private Account targetAccount; // Conta que receberá os depósitos
    private List<Long> depositSteps = new ArrayList<>(); // Passos de simulação para cada depósito
    private List<Double> depositAmounts = new ArrayList<>(); // Valores de cada depósito fracionado
    private List<Integer> depositHours = new ArrayList<>();

    private Random random = AMLSim.getRandom();

    FragmentedDepositTypology(double minAmount, double maxAmount, int startStep, int endStep) {
        super(minAmount, maxAmount, startStep, endStep);
    }

    @Override
    public void setParameters(int modelID) {
        targetAccount = alert.getMainAccount();
        if (targetAccount == null && !alert.getMembers().isEmpty()) {
            targetAccount = alert.getMembers().get(0);
        }

        depositAmounts.clear();
        depositSteps.clear();
        depositHours.clear();

        double legalLimit = AMLSim.getSimProp().getFragmentedLegalLimit();

        int minFrac = (int) Math.max(1, Math.round(AMLSim.getSimProp().getFragmentedMinFrac() * legalLimit));
        int maxFrac = (int) Math.max(1, Math.round(AMLSim.getSimProp().getFragmentedMaxFrac() * legalLimit));
        double alphaFrac = AMLSim.getSimProp().getFragmentedAlphaFrac();

        // Parâmetros da power law para o saldo líquido diário
        double minDay = AMLSim.getSimProp().getFragmentedDepositMinDay();
        double maxDay = AMLSim.getSimProp().getFragmentedDepositMaxDay();
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

            // Para cada dia da janela, sorteia o valor diário pela power law
            for (int i = 0; i < windowSize; i++) {
                double r = random.nextDouble();
                // Power law invertida
                double powMin = Math.pow(minDay, 1.0 - alphaDay);
                double powMax = Math.pow(maxDay, 1.0 - alphaDay);
                double value = Math.pow(powMin + r * (powMax - powMin), 1.0 / (1.0 - alphaDay));

                // Fragmenta o valor diário em frações menores (distribuição multimodal)
                double deposited = 0.0;
                List<Double> frags = new ArrayList<>();
                while (deposited < value) {
                    // Usar distribuição multimodal para frações em vez de power law
                    double r2 = random.nextDouble();
                    double fraction;
                    
                    if (r2 < 0.3) {  // Reduzir peso de 0.4 para 0.3
                        // Frações pequenas (log₁₀ ≈ 2.5, R$316)
                        double mu = 5.76;
                        double sigma = 2.5;  // Aumentar muito de 2.0 para 2.5 (muito espalhado)
                        fraction = Math.exp(mu + sigma * random.nextGaussian());
                    } else if (r2 < 0.7) {
                        // Frações médias (log₁₀ ≈ 3.2, R$1585)
                        double mu = 7.37;
                        double sigma = 1.3;
                        fraction = Math.exp(mu + sigma * random.nextGaussian());
                    } else {  // Aumentar peso de 0.3 para 0.4
                        // Frações grandes (log₁₀ ≈ 3.8, R$6309)
                        double mu = 8.75;
                        double sigma = 1.0;
                        fraction = Math.exp(mu + sigma * random.nextGaussian());
                    }
                    
                    // Aplicar limites min/max das frações
                    fraction = Math.max(minFrac, Math.min(maxFrac, fraction));
                    
                    double remaining = value - deposited;
                    double depositValue = Math.min(fraction, remaining);
                    frags.add(depositValue);
                    deposited += depositValue;
                }
                for (double val : frags) {
                    depositAmounts.add(val);
                    depositSteps.add(windowDays.get(i));
                    depositHours.add(0);
                }
            }
        }
    }

    @Override
    public String getModelName() {
        return "FragmentedDepositTypology";
    }

    @Override
    public void sendTransactions(long step, Account acct) {
        if (!acct.getID().equals(targetAccount.getID())) {
            return;
        }
        for (int i = 0; i < depositSteps.size(); i++) {
            if (depositSteps.get(i) == step) {
                double amount = depositAmounts.get(i);
                int hour = depositHours.get(i);

                Random rand = AMLSim.getRandom();
                double prob = rand.nextDouble();
                if (prob < 0.7) {
                    // 70%: depósito em cheque (CNAB 201)
                    CashCheckDepositModel checkModel = acct.getCashCheckDepositModel();
                    if (checkModel != null) {
                        checkModel.registerCheckDeposit(step, amount, "CHECK-DEPOSIT");
                    } else {
                        // fallback: depósito normal
                        acct.getCashInModel().registerExternalDeposit(step, amount, "FRAGMENTED_DEPOSIT");
                    }
                } else {
                    // 30%: depósito em espécie (CNAB 220)
                    CashDepositModel cashDepositModel = acct.getCashDepositModel();
                    if (cashDepositModel != null) {
                        cashDepositModel.registerCashDeposit(step, amount, "CASH-DEPOSIT");
                    } else {
                        // fallback: depósito normal
                        acct.getCashInModel().registerExternalDeposit(step, amount, "FRAGMENTED_DEPOSIT");
                    }
                }
            }
        }
    }
}