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

        // Gera os saques fracionados
        double withdrawn = 0.0;

        while (withdrawn < totalWithdrawal) {
            // Fração entre 15% e 25% do limite legal
            double minFrac = 0.15 * LEGAL_LIMIT;
            double maxFrac = 0.25 * LEGAL_LIMIT;
            double fraction = minFrac + random.nextDouble() * (maxFrac - minFrac);

            // Ajusta o valor do último saque se necessário
            double remaining = totalWithdrawal - withdrawn;
            double withdrawalValue = Math.min(fraction, remaining);

            withdrawalAmounts.add(withdrawalValue);

            // Sorteia o dia do saque dentro do intervalo
            int stepRange = (int)(endStep - startStep + 1);
            long withdrawalStep = startStep + random.nextInt(stepRange);
            withdrawalSteps.add(withdrawalStep);

            withdrawn += withdrawalValue;
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