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

    private static final double LEGAL_LIMIT = 50000.0; // Limite legal para depósito único
    private static final double MAX_TOTAL = 100000.0; // Valor máximo sorteado para depósito total

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
        // Seleciona a conta alvo (mainAccount ou primeira da lista)
        targetAccount = alert.getMainAccount();
        if (targetAccount == null && !alert.getMembers().isEmpty()) {
            targetAccount = alert.getMembers().get(0);
        }

        // Sorteia o valor total a ser depositado (entre LEGAL_LIMIT e MAX_TOTAL)
        totalDeposit = LEGAL_LIMIT + random.nextDouble() * (MAX_TOTAL - LEGAL_LIMIT);

        // Parâmetros da lei de potência para as frações
        int minFrac = (int)(0.03 * LEGAL_LIMIT); // mínimo da fração
        int maxFrac = (int)(0.15 * LEGAL_LIMIT); // máximo da fração
        double alpha = 2.2;

        depositAmounts.clear();
        depositSteps.clear();
        depositHours.clear();

        // 1. Sorteia o tamanho da faixa de dias consecutivos (ex: 1 a 5)
        int minWindow = 2;
        int maxWindow = 5;
        int windowSize = minWindow + random.nextInt(maxWindow - minWindow + 1);

        // 2. Sorteia o dia inicial da faixa dentro do intervalo permitido
        int stepRange = (int)(endStep - startStep + 1);
        if (windowSize > stepRange) {
            windowSize = stepRange; // Garante que não ultrapasse o intervalo
        }
        long windowStart = startStep + random.nextInt(stepRange - windowSize + 1);

        // 3. Gera os dias consecutivos da faixa
        List<Long> windowDays = new ArrayList<>();
        for (int i = 0; i < windowSize; i++) {
            windowDays.add((long)(windowStart + i));
        }

        // 4. Sorteia as fragmentações e distribui nos dias da faixa
        double deposited = 0.0;
        int dayIndex = 0;
        while (deposited < totalDeposit) {
            int fraction = samplePowerLaw(minFrac, maxFrac, alpha, random);
            double remaining = totalDeposit - deposited;
            double depositValue = Math.min(fraction, remaining);

            depositAmounts.add(depositValue);

            // Distribui nos dias consecutivos (cicla se tiver mais fragmentos que dias)
            long depositStep = windowDays.get(dayIndex % windowDays.size());
            depositSteps.add(depositStep);

            depositHours.add(0); // Hora não usada

            deposited += depositValue;
            dayIndex++;
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