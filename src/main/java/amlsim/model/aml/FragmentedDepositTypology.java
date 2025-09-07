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

    private static final double LEGAL_LIMIT = 50000.0;      // Limite legal para depósito único
    private static final double MAX_TOTAL = 100000.0;       // Valor máximo sorteado para depósito total

    private Account targetAccount;                          // Conta que receberá os depósitos
    private List<Long> depositSteps = new ArrayList<>();     // Passos de simulação para cada depósito
    private List<Double> depositAmounts = new ArrayList<>(); // Valores de cada depósito fracionado
    private double totalDeposit = 0.0;                      // Valor total a ser depositado
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

        // Gera os depósitos fracionados
        double deposited = 0.0;
        int stepRange = getStepRange();
        long currentStep = startStep;

        while (deposited < totalDeposit) {
            // Fração entre 15% e 25% do limite legal
            double minFrac = 0.15 * LEGAL_LIMIT;
            double maxFrac = 0.25 * LEGAL_LIMIT;
            double fraction = minFrac + random.nextDouble() * (maxFrac - minFrac);

            // Ajusta o valor do último depósito se necessário
            double remaining = totalDeposit - deposited;
            double depositValue = Math.min(fraction, remaining);

            depositAmounts.add(depositValue);

            // Todos os depósitos no mesmo dia
            depositSteps.add(startStep);

            // Sorteia hora entre 6 e 18
            int hour = 6 + random.nextInt(13);
            depositHours.add(hour);

            deposited += depositValue;
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