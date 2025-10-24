package amlsim.model.cash;

import java.util.Random;

import amlsim.AMLSim;
import amlsim.Account;
import amlsim.model.AbstractTransactionModel;

/**
 * Cash transaction model (between an account and a deposit account)
 * There are two subclasses: CashInModel (deposit) and CashOutModel (withdrawal)
 */
public abstract class CashModel extends AbstractTransactionModel {

    protected static Random rand = AMLSim.getRandom();

    // needed for cash accounts temporarily
    protected Account account;

    protected double[] randValues;  // Random values to generate transaction amounts
    protected static final int randSize = 10;  // Number of random values to be stored

    public void setAccount(Account account) {
        this.account = account;
    }

    public CashModel(){
        randValues = new double[randSize];
        for(int i = 0; i< randSize; i++){
            randValues[i] = rand.nextGaussian();  // from -1.0 to 1.0
        }
    }

    // to satisfy interface
    public void sendTransactions(long step, Account acct) {

    }

    // Abstract methods from TransactionModel
    public abstract String getModelName();  // Get transaction type description
    public abstract void makeTransaction(long step);  // Create and add transactions

    /**
     * Gera um número aleatório seguindo uma lei de potência
     * @param min Valor mínimo (ex: 1 transação)
     * @param max Valor máximo (ex: 10 transações)
     * @param alpha Expoente da lei de potência (ex: 2.2)
     * @param rand Random
     * @return Número sorteado
     */
    protected static int samplePowerLaw(int min, int max, double alpha, Random rand) {
        double r = rand.nextDouble();
        double amin = Math.pow(min, 1 - alpha);
        double amax = Math.pow(max, 1 - alpha);
        double val = Math.pow(amin + (amax - amin) * r, 1.0 / (1 - alpha));
        int result = Math.max(min, Math.min(max, (int)Math.round(val)));
        return result;
    }
}
