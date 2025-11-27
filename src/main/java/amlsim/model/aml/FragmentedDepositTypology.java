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
        targetAccount = alert.getMainAccount();
        if (targetAccount == null && !alert.getMembers().isEmpty()) {
            targetAccount = alert.getMembers().get(0);
        }

        depositAmounts.clear();
        depositSteps.clear();
        depositHours.clear();

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
            // Sorteia o valor total a ser depositado neste ciclo
            double totalDeposit = LEGAL_LIMIT + random.nextDouble() * (MAX_TOTAL - LEGAL_LIMIT);

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
            double deposited = 0.0;
            int dayIndex = 0;
            while (deposited < totalDeposit) {
                int fraction = samplePowerLaw(minFrac, maxFrac, alpha, random);
                double remaining = totalDeposit - deposited;
                double depositValue = Math.min(fraction, remaining);

                depositAmounts.add(depositValue);

                long depositStep = windowDays.get(dayIndex % windowDays.size());
                depositSteps.add(depositStep);

                depositHours.add(0);

                deposited += depositValue;
                dayIndex++;
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