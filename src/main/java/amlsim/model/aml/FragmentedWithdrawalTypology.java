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

    private static final double LEGAL_LIMIT = 50000.0;      // Limite legal para saque único
    private static final double MAX_TOTAL = 100000.0;       // Valor máximo sorteado para saque total

    private Account targetAccount;                          // Conta que fará os saques
    private List<Long> withdrawalSteps = new ArrayList<>();     // Passos de simulação para cada saque
    private List<Double> withdrawalAmounts = new ArrayList<>(); // Valores de cada saque fracionado
    private double totalWithdrawal = 0.0;                      // Valor total a ser sacado

    private Random random = AMLSim.getRandom();

    FragmentedWithdrawalTypology(double minAmount, double maxAmount, int startStep, int endStep) {
        super(minAmount, maxAmount, startStep, endStep);
    }

    @Override
    public void setParameters(int modelID) {
        // Seleciona a conta alvo (mainAccount ou primeira da lista)
        targetAccount = alert.getMainAccount();
        if (targetAccount == null && !alert.getMembers().isEmpty()) {
            targetAccount = alert.getMembers().get(0);
        }

        // Sorteia o valor total a ser sacado (entre LEGAL_LIMIT e MAX_TOTAL)
        totalWithdrawal = LEGAL_LIMIT + random.nextDouble() * (MAX_TOTAL - LEGAL_LIMIT);

        // Parâmetros da lei de potência para as frações
        int minFrac = (int)(0.03 * LEGAL_LIMIT); // mínimo da fração
        int maxFrac = (int)(0.15 * LEGAL_LIMIT); // máximo da fração
        double alpha = 2.2;

        withdrawalAmounts.clear();
        withdrawalSteps.clear();

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
        double withdrawn = 0.0;
        int dayIndex = 0;
        while (withdrawn < totalWithdrawal) {
            int fraction = samplePowerLaw(minFrac, maxFrac, alpha, random);
            double remaining = totalWithdrawal - withdrawn;
            double withdrawalValue = Math.min(fraction, remaining);

            withdrawalAmounts.add(withdrawalValue);

            // Distribui nos dias consecutivos (cicla se tiver mais fragmentos que dias)
            long withdrawalStep = windowDays.get(dayIndex % windowDays.size());
            withdrawalSteps.add(withdrawalStep);

            withdrawn += withdrawalValue;
            dayIndex++;
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