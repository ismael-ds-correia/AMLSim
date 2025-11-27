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

        withdrawalAmounts.clear();
        withdrawalSteps.clear();

        // Parâmetros da lei de potência
        int minFrac = (int)(0.05 * LEGAL_LIMIT);
        int maxFrac = (int)(0.25 * LEGAL_LIMIT);
        double alpha = 2.2;

        // Sorteia o número de ciclos de fragmentação por conta
        int minCycles = 10;
        int maxCycles = 30;
        int numCycles = samplePowerLaw(minCycles, maxCycles, alpha, random);

        int minWindow = 1;
        int maxWindow = 10;

        // Mantém os dias já usados para evitar sobreposição
        int usedStep = (int)startStep;

        for (int cycle = 0; cycle < numCycles; cycle++) {
            // Sorteia o valor total a ser sacado neste ciclo
            double totalWithdrawal = LEGAL_LIMIT + random.nextDouble() * (MAX_TOTAL - LEGAL_LIMIT);

            // Sorteia o tamanho da faixa de dias consecutivos
            int windowSize = samplePowerLaw(minWindow, maxWindow, alpha, random);

            // Sorteia o início da faixa (garante que não ultrapasse o intervalo)
            if (usedStep + windowSize > endStep) {
                usedStep = (int)startStep; // Se acabar os dias, reinicia
            }
            long windowStart = usedStep;
            usedStep += windowSize; // Atualiza para o próximo ciclo

            // Gera os dias consecutivos da faixa
            List<Long> windowDays = new ArrayList<>();
            for (int i = 0; i < windowSize; i++) {
                windowDays.add(windowStart + i);
            }

            // Fragmenta o valor e distribui nos dias da faixa
            double withdrawn = 0.0;
            int dayIndex = 0;
            while (withdrawn < totalWithdrawal) {
                int fraction = samplePowerLaw(minFrac, maxFrac, alpha, random);
                double remaining = totalWithdrawal - withdrawn;
                double withdrawalValue = Math.min(fraction, remaining);

                withdrawalAmounts.add(withdrawalValue);

                long withdrawalStep = windowDays.get(dayIndex % windowDays.size());
                withdrawalSteps.add(withdrawalStep);

                withdrawn += withdrawalValue;
                dayIndex++;
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