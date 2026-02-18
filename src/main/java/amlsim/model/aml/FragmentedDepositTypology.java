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

    private static final double LEGAL_LIMIT = 6000.0; // Limite legal para depósito único
    private static final double MAX_TOTAL = 20000.0; // Valor máximo sorteado para depósito total

    private Account targetAccount; // Conta que receberá os depósitos
    private List<Long> depositSteps = new ArrayList<>(); // Passos de simulação para cada depósito
    private List<Double> depositAmounts = new ArrayList<>(); // Valores de cada depósito fracionado
    private double totalDeposit = 0.0; // Valor total a ser depositado
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

        int minFrac = (int)(0.0007 * LEGAL_LIMIT);
        int maxFrac = (int)(0.030 * LEGAL_LIMIT);
        double alphaFrac = 2.7;

        // Parâmetros da power law para o saldo líquido diário
        double minDay = 800.0;
        double maxDay = 50000.0;
        double alphaDay = 1.6;

        int minCycles = 3;
        int maxCycles = 40;
        int numCycles = samplePowerLaw(minCycles, maxCycles, 1.5, random);

        int minWindow = 3;
        int maxWindow = 15;
        double alphaWindow = 1.5;

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

                // Fragmenta o valor diário em frações menores (também por power law)
                double deposited = 0.0;
                List<Double> frags = new ArrayList<>();
                while (deposited < value) {
                    int fraction = samplePowerLaw(minFrac, maxFrac, alphaFrac, random);
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